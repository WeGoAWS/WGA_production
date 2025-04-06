# services/auth/lambda_function.py
import json
import time
import datetime
import logging
import boto3
import uuid
from common.db import create_session, delete_session, create_or_update_user
from common.config import CONFIG
from common.utils import (
    extract_session_id_from_cookies, 
    format_api_response, 
    handle_api_exception,
    normalize_event,
    create_error_response,
    create_success_response,
)
from auth_service import (
    verify_cognito_token, 
    create_user_session, 
    logout_user, 
    validate_and_create_session,
    get_session_info
)

# 로깅 설정
logger = logging.getLogger("auth-lambda")
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda 핸들러 함수 - 통합된 인증 서비스
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    # 이벤트 정규화
    normalized_event = normalize_event(event)
    
    # 경로 및 HTTP 메서드 추출
    path = normalized_event['path']
    http_method = normalized_event['httpMethod']

    # OPTIONS 메서드 처리 (프리플라이트 요청)
    if http_method == 'OPTIONS':
        return format_api_response({
            'statusCode': 200,
            'body': json.dumps({})
        })
    
    try:
        # 엔드포인트 라우팅
        if path == '/auth' and http_method == 'GET':
            return handle_index(normalized_event)
        elif path == '/auth/logout' and http_method == 'GET' or path == '/auth/logout' and http_method == 'POST':
            return handle_logout(normalized_event)
        elif path == '/auth/verify-token' and http_method == 'POST':
            return handle_verify_token(normalized_event)
        elif path == '/auth/session' and http_method == 'GET':
            return handle_check_session(normalized_event)
        else:
            return format_api_response(404, {'error': 'Not Found'})
    except Exception as e:
        return handle_api_exception(e)

def handle_index(event):
    """
    현재 로그인 상태에 따라 사용자 정보를 반환하거나 로그인 안내 메시지를 출력합니다.
    """
    # 쿠키에서 세션 ID 추출
    headers = event.get('headers', {})
    cookie_str = headers.get('Cookie', '') or headers.get('cookie', '')
    session_id = extract_session_id_from_cookies(cookie_str)
    
    if not session_id:
        return format_api_response(200, {"message": "Hello, please login!"})
    
    # 세션 정보 조회
    session_info = get_session_info(session_id)
    if not session_info:
        return format_api_response(200, {"message": "Hello, please login!"})
    
    provider = session_info.get('provider', 'unknown')
    
    return format_api_response(200, {
        "message": f"Logged in with {provider}",
        "session_id": session_id,
        "user_sub": session_info.get('user_sub'),
        "expiration": session_info.get('expiration')
    })

def handle_logout(event):
    """
    사용자 로그아웃 처리. 세션 정보를 제거합니다.
    """
    # 쿠키에서 세션 ID 추출
    headers = event.get('headers', {})
    cookie_str = headers.get('Cookie', '') or headers.get('cookie', '')
    session_id = extract_session_id_from_cookies(cookie_str)
    
    if session_id:
        # 세션 삭제
        logout_user(session_id)
    
    # 세션 쿠키 삭제를 위한 응답 헤더 설정
    response_headers = {
        'Set-Cookie': 'session=; HttpOnly; Path=/; Max-Age=0; SameSite=Strict'
    }
    
    # 요청이 API Gateway 콘솔에서 온 것인지 확인
    if event.get('httpMethod') == 'GET':
        # GET 요청은 리다이렉트로 처리
        response_headers['Location'] = '/auth/'
        return format_api_response(302, '', response_headers)
    else:
        # POST 요청은 성공 응답으로 처리
        return format_api_response(200, {"success": True, "message": "Successfully logged out"}, response_headers)

def handle_verify_token(event):
    """
    프론트엔드에서 받은 토큰을 검증하고 유효한 경우 세션에 저장합니다.
    """
    try:
        # 요청 바디 파싱
        body = event['body']
        
        if not body or not isinstance(body, dict):
            return create_error_response("유효하지 않은 요청 형식입니다.")
        
        provider = body.get('provider', '')
        id_token = body.get('id_token', '')
        access_token = body.get('access_token', '')
        refresh_token = body.get('refresh_token', '')
        
        if not id_token or provider not in ["cognito", "google", "azure"]:
            return format_api_response(400, {"detail": "Invalid token data or unsupported provider"})
        
        # 토큰 검증 및 세션 생성
        success, session_id, claims, error_msg = validate_and_create_session(
            provider, id_token, access_token, refresh_token
        )
        
        if not success:
            return format_api_response(401, {"detail": error_msg})
        
        # 세션 만료 시간 기본값 설정
        expiration = claims.get("exp") - int(time.time())
        
        # 개발자 모드 확인 - CONFIG에서 DEVELOPER_MODE 설정 확인
        developer_mode = CONFIG.get('developer_mode', False)
        
        # 개발자 모드가 아닌 경우에만 제로 트러스트 평가 수행
        if not developer_mode:
            # 제로 트러스트 컨텍스트 평가 추가
            context = {
                'source_ip': event.get('requestContext', {}).get('identity', {}).get('sourceIp', ''),
                'user_agent': event.get('headers', {}).get('User-Agent', ''),
                'timestamp': datetime.datetime.utcnow().isoformat(),
                'mfa_used': body.get('mfa_used', False)
            }
            
            # 제로 트러스트 평가 Lambda 호출
            try:
                # AWS 세션 생성
                session = boto3.Session(region_name=CONFIG['aws_region'])
                lambda_client = session.client('lambda')
                
                payload = {
                    'body': json.dumps({
                        'user_arn': claims.get('sub'),
                        'action': 'sts:AssumeRole',  # 예시 액션
                        'resource': '*',
                        'context': context
                    })
                }
                
                response = lambda_client.invoke(
                    FunctionName=f'wga-zero-trust-enforcer-{CONFIG["env"]}',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(payload)
                )
                
                # 응답 처리
                if response.get('StatusCode') == 200:
                    zt_result = json.loads(response.get('Payload').read())
                    zt_body = json.loads(zt_result.get('body', '{}'))
                    
                    # 접근 거부 결정인 경우
                    if zt_body.get('decision') == 'deny':
                        return format_api_response(403, {
                            "detail": "Zero Trust policy denied access",
                            "risk_score": zt_body.get('risk_score'),
                            "factors": zt_body.get('factors')
                        })
                    
                    # MFA 필요 결정인 경우
                    if zt_body.get('decision') == 'require_mfa' and not context.get('mfa_used'):
                        return format_api_response(401, {
                            "detail": "Additional authentication required",
                            "require_mfa": True,
                            "risk_score": zt_body.get('risk_score')
                        })
                    
                    # 세션 만료 시간을 제로 트러스트 평가 결과에 따라 조정
                    if zt_body.get('expires_at'):
                        expiration = zt_body.get('expires_at') - int(time.time())
            except Exception as e:
                logger.error(f"Zero Trust evaluation error (proceeding with default policy): {e}", exc_info=True)
        else:
            logger.info("Developer mode is enabled. Skipping Zero Trust evaluation.")
            # 개발자 모드에서는 로그에 정보를 남기고 제로 트러스트 평가를 건너뜁니다.
        
        # 세션 쿠키 설정
        return format_api_response(
            200, 
            {"status": "success", "message": "Token verified successfully"},
            {
                'Set-Cookie': f'session={session_id}; HttpOnly; Path=/; Max-Age={expiration}; SameSite=Strict'
            }
        )
    except Exception as e:
        logger.error(f"Token verification error: {e}", exc_info=True)
        return handle_api_exception(e)

def handle_check_session(event):
    """
    현재 세션의 상태를 확인합니다.
    """
    # 쿠키에서 세션 ID 추출
    headers = event.get('headers', {})
    cookie_str = headers.get('Cookie', '') or headers.get('cookie', '')
    session_id = extract_session_id_from_cookies(cookie_str)
    
    if not session_id:
        return create_error_response("로그인 세션이 없습니다.", 401)
    
    # 세션 정보 조회
    session_info = get_session_info(session_id)
    if not session_info:
        # 세션 쿠키 삭제
        headers = {
            'Set-Cookie': "session=; HttpOnly; Path=/; Max-Age=0; SameSite=Strict"
        }
        
        return format_api_response(
            401,
            {'success': False, 'message': '세션이 만료되었습니다.'},
            headers
        )
    
    # 세션 유효성 확인
    expiration = session_info.get('expiration', 0)
    now = int(time.time())
    
    if expiration < now:
        # 세션 쿠키 삭제
        headers = {
            'Set-Cookie': "session=; HttpOnly; Path=/; Max-Age=0; SameSite=Strict"
        }
        
        return format_api_response(
            401,
            {'success': False, 'message': '세션이 만료되었습니다.'},
            headers
        )
    
    # 사용자 정보 추출
    user_info = {
        'sub': session_info.get('user_sub'),
        'provider': session_info.get('provider'),
        'id_token': session_info.get('id_token')
    }
    
    return create_success_response({
        'user': user_info,
        'expiration': expiration,
        'remaining': expiration - now
    })