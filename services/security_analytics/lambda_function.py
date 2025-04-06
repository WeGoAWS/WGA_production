# services/security_analytics/lambda_function.py
import json
import boto3
import time
import datetime
import uuid
from common.db import create_analysis_result, get_anomaly_events_by_user
from common.utils import (
    extract_session_id_from_cookies, 
    format_api_response, 
    handle_api_exception, 
    get_aws_session, 
    get_id_token_from_session,
    normalize_event,
    create_error_response,
    create_success_response,
    publish_to_sns,

)
from analytics_service import (
    analyze_user_behavior, 
    detect_account_anomalies, 
    get_user_risk_score,
    update_user_profile
)
from common.config import CONFIG

import logging
logger = logging.getLogger("security-analytics")
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda 핸들러 함수 - 통합된 보안 분석 서비스
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    # 이벤트 정규화
    normalized_event = normalize_event(event)
    
    # OPTIONS 메서드 처리 (프리플라이트 요청)
    if normalized_event.get('httpMethod') == 'OPTIONS':
        return format_api_response(200, {})
    
    try:
        # 엔드포인트 라우팅
        if path.startswith('/security-analytics/analyze-user'):
            return analyze_user_behavior_handler(normalized_event)
        elif path.startswith('/security-analytics/detect-anomalies'):
            return detect_anomalies_handler(normalized_event)
        elif path.startswith('/security-analytics/get-risk-score'):
            return get_risk_score_handler(normalized_event)
        elif path.startswith('/security-analytics/get-anomaly-events'):
            return get_anomaly_events_handler(normalized_event)
        elif path.startswith('/security-analytics/test'):
            return test(normalized_event)
        else:
            return format_api_response(404, {'error': 'Not Found'})
    except Exception as e:
        return handle_api_exception(e)

def analyze_user_behavior_handler(event):
    """
    사용자 행동 분석 및 프로파일 업데이트 처리
    """
    query_params = event.get('queryParameters', {})
    id_token = event.get('id_token')
    
    # 인증 확인
    if not id_token:
        return create_error_response("인증이 필요합니다.", 401)
    
    # 파라미터 검증
    user_arn = query_params.get('user_arn')
    if not user_arn:
        return create_error_response("사용자 ARN이 필요합니다.")
    
    # 분석 기간 파라미터 처리
    try:
        days = int(query_params.get('days', 30))
    except ValueError:
        days = 30
    
    # AWS 세션 생성
    try:
        session = get_aws_session(id_token)
    except Exception as e:
        logger.error(f"AWS 세션 생성 실패: {e}", exc_info=True)
        return create_error_response("AWS 세션 생성 중 오류가 발생했습니다.", 500)
    
    # 사용자 행동 분석 수행
    try:
        analysis_result = analyze_user_behavior(session, user_arn, days)
        
        # 사용자 프로파일 업데이트
        profile_updated = update_user_profile(user_arn, analysis_result)
        
        # 분석 결과 저장 (DynamoDB)
        result_id = create_analysis_result({
            'id': str(uuid.uuid4()),
            'user_arn': user_arn,
            'type': 'behavior_analysis',
            'date': datetime.datetime.utcnow().strftime('%Y-%m-%d'),
            'analysis_timestamp': analysis_result.get('analyzed_at', datetime.datetime.utcnow().isoformat()),
            'period_days': days,
            'events_analyzed': analysis_result.get('events_analyzed', 0),
            'risk_score': analysis_result.get('profile_data', {}).get('risk_score', 50),
            'created_at': int(time.time())
        })
        
        # 응답 구성
        response_data = {
            'analysis_id': result_id,
            'user_arn': user_arn,
            'profile_updated': profile_updated,
            'analyzed_at': analysis_result.get('analyzed_at'),
            'period_days': days,
            'events_analyzed': analysis_result.get('events_analyzed', 0),
            'risk_score': analysis_result.get('profile_data', {}).get('risk_score', 50),
            'top_services': analysis_result.get('top_services', [])[:5],
            'unused_permissions': len(analysis_result.get('unused_permissions', [])),
            'result_summary': "사용자 행동 분석이 완료되었습니다."
        }
        
        return create_success_response(response_data)
    except Exception as e:
        logger.error(f"사용자 행동 분석 중 오류: {e}", exc_info=True)
        return create_error_response(f"분석 중 오류가 발생했습니다: {str(e)}", 500)

def detect_anomalies_handler(event):
    """
    계정 전체 이상 행동 탐지 처리
    """
    query_params = event.get('queryParameters', {})
    id_token = event.get('id_token')
    
    # 인증 확인
    if not id_token:
        return create_error_response("인증이 필요합니다.", 401)
    
    # 분석 기간 파라미터 처리
    try:
        days = int(query_params.get('days', 7))
    except ValueError:
        days = 7
    
    # AWS 세션 생성
    try:
        session = get_aws_session(id_token)
    except Exception as e:
        logger.error(f"AWS 세션 생성 실패: {e}", exc_info=True)
        return create_error_response("AWS 세션 생성 중 오류가 발생했습니다.", 500)
    
    # 이상 행동 탐지 수행
    try:
        detection_result = detect_account_anomalies(session, days)
        
        # 심각한 이상 행동이 있는 경우 SNS 알림 발행
        if detection_result.get('anomalies_detected', 0) > 0:
            high_risk_anomalies = [a for a in detection_result.get('anomalies', []) if a.get('risk_score', 0) >= 70]
            
            if high_risk_anomalies:
                alert_data = {
                    'account_id': detection_result.get('account_id'),
                    'timestamp': datetime.datetime.utcnow().isoformat(),
                    'high_risk_anomalies': len(high_risk_anomalies),
                    'anomalies': high_risk_anomalies
                }
                
                publish_to_sns(
                    session, 
                    CONFIG['sns']['anomaly_alert_topic'],
                    alert_data,
                    subject=f"보안 경고: {len(high_risk_anomalies)}개의 고위험 이상 행동 탐지됨"
                )
        
        # 응답 구성
        response_data = {
            'account_id': detection_result.get('account_id'),
            'analyzed_at': detection_result.get('analyzed_at'),
            'period_days': days,
            'events_analyzed': detection_result.get('events_analyzed', 0),
            'unique_users': detection_result.get('unique_users', 0),
            'anomalies_detected': detection_result.get('anomalies_detected', 0),
            'anomalies': detection_result.get('anomalies', [])
        }
        
        return create_success_response(response_data)
    except Exception as e:
        logger.error(f"이상 행동 탐지 중 오류: {e}", exc_info=True)
        return create_error_response(f"이상 행동 탐지 중 오류가 발생했습니다: {str(e)}", 500)

def get_risk_score_handler(event):
    """
    사용자 위험 점수 조회 처리
    """
    query_params = event.get('queryParameters', {})
    id_token = event.get('id_token')
    
    # 인증 확인
    if not id_token:
        return create_error_response("인증이 필요합니다.", 401)
    
    # 파라미터 검증
    user_arn = query_params.get('user_arn')
    if not user_arn:
        return create_error_response("사용자 ARN이 필요합니다.")
    
    # AWS 세션 생성
    try:
        session = get_aws_session(id_token)
    except Exception as e:
        logger.error(f"AWS 세션 생성 실패: {e}", exc_info=True)
        return create_error_response("AWS 세션 생성 중 오류가 발생했습니다.", 500)
    
    # 위험 점수 조회
    try:
        risk_score_result = get_user_risk_score(session, user_arn)
        
        return create_success_response(risk_score_result)
    except Exception as e:
        logger.error(f"위험 점수 조회 중 오류: {e}", exc_info=True)
        return create_error_response(f"위험 점수 조회 중 오류가 발생했습니다: {str(e)}", 500)

def get_anomaly_events_handler(event):
    """
    사용자의 이상 행동 이벤트 목록 조회 처리
    """
    query_params = event.get('queryParameters', {})
    id_token = event.get('id_token')
    
    # 인증 확인
    if not id_token:
        return create_error_response("인증이 필요합니다.", 401)
    
    # 파라미터 검증
    user_arn = query_params.get('user_arn')
    if not user_arn:
        return create_error_response("사용자 ARN이 필요합니다.")
    
    # 제한 파라미터 처리
    try:
        limit = int(query_params.get('limit', 20))
    except ValueError:
        limit = 20
    
    # 이상 행동 이벤트 조회
    try:
        anomaly_events = get_anomaly_events_by_user(user_arn, limit)
        
        # 응답 구성
        response_data = {
            'user_arn': user_arn,
            'total_events': len(anomaly_events),
            'events': anomaly_events
        }
        
        return create_success_response(response_data)
    except Exception as e:
        logger.error(f"이상 행동 이벤트 조회 중 오류: {e}", exc_info=True)
        return create_error_response(f"이상 행동 이벤트 조회 중 오류가 발생했습니다: {str(e)}", 500)

def test(event):
    # id_token 검증 안함
    
    response_data = {
        "user_arn": "arn:aws:iam::123456789012:user/dev_user",
        "request_summary": "사용자가 S3 버킷을 생성하기 위한 권한 요청",
        "request_policy": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:CreateBucket",
                        "s3:PutBucketPolicy",
                        "s3:PutBucketAcl",
                        "s3:PutEncryptionConfiguration",
                        "s3:PutBucketTagging"
                    ],
                    "Resource": "arn:aws:s3:::*"
                }
            ]
        }
    }
    return create_success_response(response_data)