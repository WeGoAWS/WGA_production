# services/security_analytics/analytics_service.py
import json
import boto3
import time
import datetime
import uuid
import numpy as np
from common.config import CONFIG
from common.db import (
    get_user_activity_profile, 
    update_user_activity_profile, 
    save_anomaly_event, 
    create_analysis_result
)
from common.utils import upload_to_s3, publish_to_sns

import logging
logger = logging.getLogger("security-analytics")
logger.setLevel(logging.INFO)

# 사용자 행동 프로파일 관련 함수들
def analyze_user_behavior(session, user_arn, days=30):
    """
    사용자의 행동 패턴을 분석하고 프로파일을 구성합니다.
    
    Args:
        session (boto3.Session): AWS 세션
        user_arn (str): 사용자 ARN
        days (int): 분석 기간(일)
        
    Returns:
        dict: 분석 결과
    """
    logger.info(f"사용자 행동 분석 시작: {user_arn}, 기간: {days}일")
    
    # 기존 프로파일 조회
    profile = get_user_activity_profile(user_arn)
    
    # CloudTrail 로그 분석
    cloudtrail_events = get_user_cloudtrail_events(session, user_arn, days)
    
    # 필요 권한 분석
    required_permissions = analyze_required_permissions(cloudtrail_events)
    
    # 접근 패턴 분석
    access_patterns = analyze_access_patterns(cloudtrail_events)
    
    # 서비스 사용 패턴 분석
    service_usage = analyze_service_usage(cloudtrail_events)
    
    # 행동 시퀀스 분석
    action_sequences = analyze_action_sequences(cloudtrail_events)
    
    # 위치 및 IP 분석
    locations = analyze_locations(cloudtrail_events)
    
    # 시간 패턴 분석
    time_patterns = analyze_time_patterns(cloudtrail_events)
    
    # 프로파일 데이터 구성
    profile_data = {
        'user_arn': user_arn,
        'last_analyzed': datetime.datetime.utcnow().isoformat(),
        'analyzed_days': days,
        'required_permissions': required_permissions,
        'access_patterns': access_patterns,
        'service_usage': service_usage,
        'action_sequences': action_sequences,
        'locations': locations,
        'ip_addresses': extract_ip_addresses(cloudtrail_events),
        'normal_patterns': time_patterns,
        'risk_score': calculate_user_risk_score(required_permissions, service_usage),
        'events_count': len(cloudtrail_events)
    }
    
    # 분석 결과 저장
    result = {
        'user_arn': user_arn,
        'analyzed_at': datetime.datetime.utcnow().isoformat(),
        'period_days': days,
        'profile_data': profile_data,
        'events_analyzed': len(cloudtrail_events),
        'top_services': list(service_usage.get('service_counts', {}).items())[:5],
        'unused_permissions': identify_unused_permissions(session, user_arn, required_permissions)
    }
    
    return result

def get_user_cloudtrail_events(session, user_arn, days=30):
    """
    CloudTrail에서 사용자의 이벤트를 조회합니다.
    
    Args:
        session (boto3.Session): AWS 세션
        user_arn (str): 사용자 ARN
        days (int): 조회 기간(일)
        
    Returns:
        list: CloudTrail 이벤트 목록
    """
    cloudtrail_client = session.client("cloudtrail")
    
    # 시간 범위 설정
    end_time = datetime.datetime.utcnow()
    start_time = end_time - datetime.timedelta(days=days)
    
    # 이벤트 조회 파라미터
    params = {
        "LookupAttributes": [
            {
                "AttributeKey": "Username",
                "AttributeValue": user_arn
            }
        ],
        "StartTime": start_time,
        "EndTime": end_time,
        "MaxResults": 1000  # 최대 결과 수
    }
    
    events = []
    try:
        # 이벤트 조회 (페이지네이션 처리)
        has_more = True
        next_token = None
        
        while has_more:
            if next_token:
                params['NextToken'] = next_token
            
            response = cloudtrail_client.lookup_events(**params)
            events.extend(response.get("Events", []))
            
            next_token = response.get("NextToken")
            has_more = next_token is not None
            
            # API 호출 제한을 피하기 위한 지연
            if has_more:
                time.sleep(0.2)
        
        logger.info(f"사용자 {user_arn}의 CloudTrail 이벤트 {len(events)}개 조회됨")
        return events
    except Exception as e:
        logger.error(f"CloudTrail 이벤트 조회 오류: {e}", exc_info=True)
        return []

def analyze_required_permissions(events):
    """
    사용자가 실제로 사용한 권한을 분석합니다.
    
    Args:
        events (list): CloudTrail 이벤트 목록
        
    Returns:
        list: 필요한 권한 목록
    """
    permissions = set()
    
    for event in events:
        event_name = event.get("EventName", "")
        event_source = event.get("EventSource", "")
        
        if event_source.endswith(".amazonaws.com"):
            # 서비스 이름 추출 (예: s3.amazonaws.com -> s3)
            service = event_source.split(".")[0]
            
            # EventName을 IAM 권한 형식으로 변환 (예: GetObject -> s3:GetObject)
            permission = f"{service}:{event_name}"
            permissions.add(permission)
    
    return list(permissions)

def analyze_access_patterns(events):
    """
    리소스 접근 패턴을 분석합니다.
    
    Args:
        events (list): CloudTrail 이벤트 목록
        
    Returns:
        dict: 접근 패턴 정보
    """
    resource_types = {}
    resource_names = {}
    
    for event in events:
        # CloudTrail 이벤트에서 리소스 정보 추출
        resources = []
        
        # CloudTrail v1 형식
        if 'Resources' in event:
            resources = event.get('Resources', [])
        # CloudTrail 이벤트를 직접 파싱한 경우
        elif 'CloudTrailEvent' in event:
            try:
                ct_event = json.loads(event['CloudTrailEvent'])
                resources = ct_event.get('resources', [])
            except (json.JSONDecodeError, KeyError):
                continue
        
        for resource in resources:
            resource_type = resource.get('ResourceType', '')
            resource_name = resource.get('ResourceName', '')
            
            if resource_type:
                resource_types[resource_type] = resource_types.get(resource_type, 0) + 1
            
            if resource_name:
                resource_names[resource_name] = resource_names.get(resource_name, 0) + 1
    
    return {
        'resource_type_counts': resource_types,
        'resource_name_counts': resource_names
    }

def analyze_service_usage(events):
    """
    서비스 사용 패턴을 분석합니다.
    
    Args:
        events (list): CloudTrail 이벤트 목록
        
    Returns:
        dict: 서비스 사용 정보
    """
    service_counts = {}
    api_counts = {}
    frequent_apis = []
    
    for event in events:
        event_name = event.get("EventName", "")
        event_source = event.get("EventSource", "")
        
        if event_source.endswith(".amazonaws.com"):
            service = event_source.split(".")[0]
            service_counts[service] = service_counts.get(service, 0) + 1
            api_counts[event_name] = api_counts.get(event_name, 0) + 1
    
    # 자주 사용되는 API 추출 (상위 20개)
    sorted_apis = sorted(api_counts.items(), key=lambda x: x[1], reverse=True)
    frequent_apis = [api[0] for api in sorted_apis[:20]]
    
    return {
        'service_counts': service_counts,
        'api_counts': api_counts,
        'frequent_apis': frequent_apis
    }

def analyze_action_sequences(events):
    """
    사용자의 액션 시퀀스 패턴을 분석합니다.
    
    Args:
        events (list): CloudTrail 이벤트 목록
        
    Returns:
        dict: 액션 시퀀스 정보
    """
    # 이벤트를 시간순으로 정렬
    sorted_events = sorted(events, key=lambda x: x.get('EventTime', ''))
    
    sequences = {}
    prev_event = None
    
    for event in sorted_events:
        event_name = event.get("EventName", "")
        
        if prev_event:
            prev_name = prev_event.get("EventName", "")
            sequence = f"{prev_name} -> {event_name}"
            sequences[sequence] = sequences.get(sequence, 0) + 1
        
        prev_event = event
    
    # 가장 빈번한 시퀀스 추출 (상위 10개)
    sorted_sequences = sorted(sequences.items(), key=lambda x: x[1], reverse=True)
    top_sequences = {seq[0]: seq[1] for seq in sorted_sequences[:10]}
    
    return {
        'top_sequences': top_sequences
    }

def analyze_locations(events):
    """
    접속 위치 정보를 분석합니다.
    
    Args:
        events (list): CloudTrail 이벤트 목록
        
    Returns:
        list: 위치 정보 목록
    """
    locations = {}
    
    for event in events:
        # CloudTrail 이벤트에서 위치 정보 추출
        source_ip = None
        
        # CloudTrail v1 형식
        if 'SourceIPAddress' in event:
            source_ip = event.get('SourceIPAddress')
        # CloudTrail 이벤트를 직접 파싱한 경우
        elif 'CloudTrailEvent' in event:
            try:
                ct_event = json.loads(event['CloudTrailEvent'])
                source_ip = ct_event.get('sourceIPAddress')
            except (json.JSONDecodeError, KeyError):
                continue
        
        if source_ip:
            # IP를 위치 정보로 변환하는 로직은 실제 구현 필요
            # 여기서는 IP 자체를 키로 사용
            locations[source_ip] = locations.get(source_ip, 0) + 1
    
    # 가장 빈번한 위치 추출
    sorted_locations = sorted(locations.items(), key=lambda x: x[1], reverse=True)
    
    # 임시 위치 정보 구성 (실제로는 GeoIP 서비스 사용 필요)
    location_list = []
    for ip, count in sorted_locations[:5]:
        location_list.append({
            'ip': ip,
            'country': 'Unknown',  # GeoIP 서비스로 채워야 함
            'city': 'Unknown',     # GeoIP 서비스로 채워야 함
            'count': count
        })
    
    return location_list

def extract_ip_addresses(events):
    """
    이벤트에서 IP 주소 목록을 추출합니다.
    
    Args:
        events (list): CloudTrail 이벤트 목록
        
    Returns:
        list: IP 주소 목록
    """
    ip_addresses = set()
    
    for event in events:
        # CloudTrail v1 형식
        if 'SourceIPAddress' in event:
            ip = event.get('SourceIPAddress')
            if ip and ip != 'AWS Internal':
                ip_addresses.add(ip)
        # CloudTrail 이벤트를 직접 파싱한 경우
        elif 'CloudTrailEvent' in event:
            try:
                ct_event = json.loads(event['CloudTrailEvent'])
                ip = ct_event.get('sourceIPAddress')
                if ip and ip != 'AWS Internal':
                    ip_addresses.add(ip)
            except (json.JSONDecodeError, KeyError):
                continue
    
    return list(ip_addresses)

def analyze_time_patterns(events):
    """
    접속 시간 패턴을 분석합니다.
    
    Args:
        events (list): CloudTrail 이벤트 목록
        
    Returns:
        dict: 시간 패턴 정보
    """
    hour_counts = {i: 0 for i in range(24)}
    day_counts = {i: 0 for i in range(7)}
    
    for event in events:
        event_time_str = event.get('EventTime')
        if not event_time_str:
            continue
        
        try:
            # ISO 형식 시간 문자열 파싱
            event_time = datetime.datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
            hour = event_time.hour
            day = event_time.weekday()
            
            hour_counts[hour] += 1
            day_counts[day] += 1
        except (ValueError, TypeError):
            continue
    
    # 활동이 많은 시간대 추출
    active_hours = [hour for hour, count in hour_counts.items() 
                   if count > sum(hour_counts.values()) / 48]  # 평균의 2배 이상
    
    # 활동이 많은 요일 추출
    active_days = [day for day, count in day_counts.items() 
                   if count > sum(day_counts.values()) / 14]  # 평균의 2배 이상
    
    return {
        'hour_counts': hour_counts,
        'day_counts': day_counts,
        'active_hours': active_hours,
        'primary_days': active_days
    }

def calculate_user_risk_score(required_permissions, service_usage):
    """
    사용자의 위험 점수를 계산합니다.
    
    Args:
        required_permissions (list): 필요한 권한 목록
        service_usage (dict): 서비스 사용 정보
        
    Returns:
        int: 위험 점수 (0-100)
    """
    # 기본 점수
    score = 0
    
    # 권한 수에 따른 점수 (많을수록 위험)
    perms_count = len(required_permissions)
    if perms_count > 100:
        score += 40
    elif perms_count > 50:
        score += 30
    elif perms_count > 20:
        score += 20
    elif perms_count > 10:
        score += 10
    
    # 민감한 서비스 사용 여부에 따른 점수
    sensitive_services = {
        "iam": 30,
        "kms": 25,
        "lambda": 15,
        "ec2": 10,
        "s3": 5
    }
    
    service_counts = service_usage.get('service_counts', {})
    for service, points in sensitive_services.items():
        if service in service_counts:
            score += points
    
    # 권한 복잡도에 따른 점수
    wildcard_count = 0
    for perm in required_permissions:
        if perm.endswith(':*'):
            wildcard_count += 1
    
    if wildcard_count > 5:
        score += 20
    elif wildcard_count > 0:
        score += 10
    
    # 최대 100점으로 제한
    return min(100, score)

def identify_unused_permissions(session, user_arn, used_permissions):
    """
    사용자에게 할당되었지만 사용되지 않은 권한을 식별합니다.
    
    Args:
        session (boto3.Session): AWS 세션
        user_arn (str): 사용자 ARN
        used_permissions (list): 실제로 사용된 권한 목록
        
    Returns:
        list: 사용되지 않은 권한 목록
    """
    # ARN에서 사용자 이름 추출
    user_name = None
    if ":user/" in user_arn:
        user_name = user_arn.split("/")[-1]
    elif ":assumed-role/" in user_arn:
        # 역할인 경우 사용자 이름 추출 불가
        return []
    
    if not user_name:
        return []
    
    try:
        # 사용자 권한 조회
        iam_client = session.client("iam")
        
        # 인라인 정책 조회
        policy_names = iam_client.list_user_policies(UserName=user_name).get("PolicyNames", [])
        
        all_permissions = set()
        
        for policy_name in policy_names:
            policy_response = iam_client.get_user_policy(
                UserName=user_name,
                PolicyName=policy_name
            )
            
            policy_document = policy_response.get("PolicyDocument", {})
            
            # 정책에서 권한 추출
            for statement in policy_document.get("Statement", []):
                if statement.get("Effect") == "Allow":
                    actions = statement.get("Action", [])
                    
                    # 문자열인 경우 리스트로 변환
                    if isinstance(actions, str):
                        actions = [actions]
                    
                    for action in actions:
                        all_permissions.add(action)
        
        # 관리형 정책 조회
        attached_policies = iam_client.list_attached_user_policies(UserName=user_name).get("AttachedPolicies", [])
        
        for policy in attached_policies:
            policy_arn = policy.get("PolicyArn")
            policy_version = iam_client.get_policy(PolicyArn=policy_arn).get("Policy", {}).get("DefaultVersionId")
            
            policy_version_response = iam_client.get_policy_version(
                PolicyArn=policy_arn,
                VersionId=policy_version
            )
            
            version_document = policy_version_response.get("PolicyVersion", {}).get("Document", {})
            
            # 정책에서 권한 추출
            for statement in version_document.get("Statement", []):
                if statement.get("Effect") == "Allow":
                    actions = statement.get("Action", [])
                    
                    # 문자열인 경우 리스트로 변환
                    if isinstance(actions, str):
                        actions = [actions]
                    
                    for action in actions:
                        all_permissions.add(action)
        
        # 사용된 권한을 제외한 사용되지 않은 권한 목록 생성
        unused_permissions = set(all_permissions) - set(used_permissions)
        
        return list(unused_permissions)
    except Exception as e:
        logger.error(f"사용되지 않은 권한 식별 오류: {e}", exc_info=True)
        return []

def update_user_profile(user_arn, analysis_result):
    """
    사용자 프로파일을 업데이트합니다.
    
    Args:
        user_arn (str): 사용자 ARN
        analysis_result (dict): 분석 결과
        
    Returns:
        bool: 성공 여부
    """
    try:
        # 프로파일 업데이트
        profile_data = analysis_result.get('profile_data', {})
        if not profile_data:
            logger.error(f"사용자 {user_arn}의 프로파일 데이터가 없습니다.")
            return False
        
        # 기존 프로파일 조회
        existing_profile = get_user_activity_profile(user_arn)
        
        # 기존 프로파일이 있으면 병합
        if existing_profile:
            # 기존 프로파일 데이터 복사
            merged_profile = existing_profile.copy()
            
            # 새 프로파일 데이터 적용
            for key, value in profile_data.items():
                if key != 'user_arn':  # 사용자 ARN은 변경 불가
                    merged_profile[key] = value
            
            # 업데이트 타임스탬프 갱신
            merged_profile['updated_at'] = int(time.time())
            
            return update_user_activity_profile(user_arn, merged_profile)
        else:
            # 새 프로파일 생성
            return update_user_activity_profile(user_arn, profile_data)
    except Exception as e:
        logger.error(f"사용자 프로파일 업데이트 오류: {e}", exc_info=True)
        return False

# 이상 탐지 관련 함수들
def detect_account_anomalies(session, days=7):
    """
    계정 전체의 이상 행동을 탐지합니다.
    
    Args:
        session (boto3.Session): AWS 세션
        days (int): 분석 기간(일)
        
    Returns:
        dict: 이상 탐지 결과
    """
    logger.info(f"계정 이상 행동 탐지 시작 (기간: {days}일)")
    
    # 계정 ID 조회
    sts_client = session.client('sts')
    account_id = sts_client.get_caller_identity().get('Account')
    
    # CloudTrail 이벤트 조회
    cloudtrail_client = session.client("cloudtrail")
    
    # 시간 범위 설정
    end_time = datetime.datetime.utcnow()
    start_time = end_time - datetime.timedelta(days=days)
    
    # 이벤트 조회 파라미터
    params = {
        "StartTime": start_time,
        "EndTime": end_time,
        "MaxResults": 1000  # 최대 결과 수
    }
    
    events = []
    try:
        # 이벤트 조회 (페이지네이션 처리)
        has_more = True
        next_token = None
        
        while has_more and len(events) < 5000:  # 최대 5,000개까지 조회
            if next_token:
                params['NextToken'] = next_token
            
            response = cloudtrail_client.lookup_events(**params)
            events.extend(response.get("Events", []))
            
            next_token = response.get("NextToken")
            has_more = next_token is not None
            
            # API 호출 제한을 피하기 위한 지연
            if has_more:
                time.sleep(0.2)
        
        logger.info(f"계정 {account_id}의 CloudTrail 이벤트 {len(events)}개 조회됨")
        
        # 사용자별 이벤트 그룹화
        user_events = {}
        for event in events:
            username = event.get('Username', 'unknown')
            if username not in user_events:
                user_events[username] = []
            user_events[username].append(event)
        
        # 사용자별 이상 행동 탐지
        anomalies = []
        for username, user_event_list in user_events.items():
            if username == 'unknown' or not user_event_list:
                continue
            
            user_anomalies = detect_user_anomalies(session, username, user_event_list)
            if user_anomalies:
                anomalies.extend(user_anomalies)
        
        # 이상 행동 이벤트 저장
        for anomaly in anomalies:
            save_anomaly_event(anomaly)
        
        # 결과 구성
        result = {
            'account_id': account_id,
            'analyzed_at': datetime.datetime.utcnow().isoformat(),
            'period_days': days,
            'events_analyzed': len(events),
            'unique_users': len(user_events),
            'anomalies_detected': len(anomalies),
            'anomalies': anomalies[:10]  # 최대 10개까지 반환
        }
        
        return result
    except Exception as e:
        logger.error(f"계정 이상 행동 탐지 오류: {e}", exc_info=True)
        return {
            'error': str(e),
            'account_id': account_id,
            'analyzed_at': datetime.datetime.utcnow().isoformat()
        }

def detect_user_anomalies(session, username, events):
    """
    특정 사용자의 이벤트에서 이상 행동을 탐지합니다.
    
    Args:
        session (boto3.Session): AWS 세션
        username (str): 사용자명
        events (list): 사용자의 CloudTrail 이벤트 목록
        
    Returns:
        list: 이상 행동 목록
    """
    logger.info(f"사용자 {username}의 이상 행동 탐지 시작 (이벤트 수: {len(events)})")
    
    # 기존 사용자 프로파일 조회
    profile = get_user_activity_profile(username)
    
    # 프로파일이 없는 경우 이상 행동을 판단할 기준이 없음
    if not profile:
        logger.info(f"사용자 {username}의 프로파일이 없어 이상 탐지를 건너뜁니다.")
        return []
    
    anomalies = []
    
    # 1. 비정상적인 위치/IP 탐지
    ip_anomalies = detect_ip_anomalies(username, events, profile)
    anomalies.extend(ip_anomalies)
    
    # 2. 비정상적인 서비스 사용 탐지
    service_anomalies = detect_service_anomalies(username, events, profile)
    anomalies.extend(service_anomalies)
    
    # 3. 비정상적인 액션 패턴 탐지
    action_anomalies = detect_action_anomalies(username, events, profile)
    anomalies.extend(action_anomalies)
    
    # 4. 비정상적인 시간 패턴 탐지
    time_anomalies = detect_time_anomalies(username, events, profile)
    anomalies.extend(time_anomalies)
    
    # 5. 권한 오용 탐지
    privilege_anomalies = detect_privilege_abuse(username, events, profile)
    anomalies.extend(privilege_anomalies)
    
    return anomalies

def detect_ip_anomalies(username, events, profile):
    """
    비정상적인 IP 접속을 탐지합니다.
    
    Args:
        username (str): 사용자명
        events (list): 사용자의 CloudTrail 이벤트 목록
        profile (dict): 사용자 프로파일
        
    Returns:
        list: IP 관련 이상 행동 목록
    """
    known_ips = profile.get('ip_addresses', [])
    anomalies = []
    
    for event in events:
        source_ip = None
        
        # CloudTrail v1 형식
        if 'SourceIPAddress' in event:
            source_ip = event.get('SourceIPAddress')
        # CloudTrail 이벤트를 직접 파싱한 경우
        elif 'CloudTrailEvent' in event:
            try:
                ct_event = json.loads(event['CloudTrailEvent'])
                source_ip = ct_event.get('sourceIPAddress')
            except (json.JSONDecodeError, KeyError):
                continue
        
        if source_ip and source_ip != 'AWS Internal' and source_ip not in known_ips:
            # 모든 이벤트를 저장하지 않고, 최초 발견된 새 IP에 대해서만 이상 행동으로 기록
            if not any(a.get('source_ip') == source_ip for a in anomalies):
                anomaly = {
                    'id': str(uuid.uuid4()),
                    'user_arn': username,
                    'timestamp': int(time.time()),
                    'event_time': event.get('EventTime'),
                    'anomaly_type': 'new_ip_address',
                    'source_ip': source_ip,
                    'event_name': event.get('EventName'),
                    'risk_score': 60,  # 새 IP는 중간 위험도
                    'details': {
                        'known_ips': known_ips,
                        'event_id': event.get('EventId')
                    }
                }
                anomalies.append(anomaly)
    
    return anomalies

def detect_service_anomalies(username, events, profile):
    """
    비정상적인 서비스 사용을 탐지합니다.
    
    Args:
        username (str): 사용자명
        events (list): 사용자의 CloudTrail 이벤트 목록
        profile (dict): 사용자 프로파일
        
    Returns:
        list: 서비스 관련 이상 행동 목록
    """
    service_usage = profile.get('service_usage', {})
    common_services = service_usage.get('service_counts', {}).keys()
    anomalies = []
    
    for event in events:
        event_source = event.get('EventSource', '')
        
        if event_source.endswith('.amazonaws.com'):
            service = event_source.split('.')[0]
            
            if service not in common_services:
                # 모든 이벤트를 저장하지 않고, 최초 발견된 새 서비스에 대해서만 이상 행동으로 기록
                if not any(a.get('service') == service for a in anomalies):
                    anomaly = {
                        'id': str(uuid.uuid4()),
                        'user_arn': username,
                        'timestamp': int(time.time()),
                        'event_time': event.get('EventTime'),
                        'anomaly_type': 'new_service_usage',
                        'service': service,
                        'event_name': event.get('EventName'),
                        'risk_score': 50,  # 새 서비스는 중간 위험도
                        'details': {
                            'common_services': list(common_services),
                            'event_id': event.get('EventId')
                        }
                    }
                    anomalies.append(anomaly)
    
    return anomalies

def detect_action_anomalies(username, events, profile):
    """
    비정상적인 액션 패턴을 탐지합니다.
    
    Args:
        username (str): 사용자명
        events (list): 사용자의 CloudTrail 이벤트 목록
        profile (dict): 사용자 프로파일
        
    Returns:
        list: 액션 관련 이상 행동 목록
    """
    service_usage = profile.get('service_usage', {})
    frequent_apis = service_usage.get('frequent_apis', [])
    anomalies = []
    
    # 민감한 액션 목록
    sensitive_actions = [
        'DeleteUser', 'CreateUser', 'CreateAccessKey', 'PutRolePolicy',
        'DeleteDBInstance', 'StopInstances', 'TerminateInstances',
        'DeleteBucket', 'UpdateUser', 'DetachRolePolicy'
    ]
    
    for event in events:
        event_name = event.get('EventName', '')
        
        # 민감한 액션 탐지
        if event_name in sensitive_actions:
            anomaly = {
                'id': str(uuid.uuid4()),
                'user_arn': username,
                'timestamp': int(time.time()),
                'event_time': event.get('EventTime'),
                'anomaly_type': 'sensitive_action',
                'action': event_name,
                'event_name': event_name,
                'risk_score': 75,  # 민감한 액션은 높은 위험도
                'details': {
                    'event_id': event.get('EventId'),
                    'event_source': event.get('EventSource')
                }
            }
            anomalies.append(anomaly)
        
        # 새로운 API 호출 탐지
        elif event_name not in frequent_apis:
            # 너무 많은 이상 행동이 생성되지 않도록 일부 제한
            if len(anomalies) < 10 and not any(a.get('action') == event_name for a in anomalies):
                anomaly = {
                    'id': str(uuid.uuid4()),
                    'user_arn': username,
                    'timestamp': int(time.time()),
                    'event_time': event.get('EventTime'),
                    'anomaly_type': 'new_api_call',
                    'action': event_name,
                    'event_name': event_name,
                    'risk_score': 40,  # 새로운 API는 중간 위험도
                    'details': {
                        'frequent_apis': frequent_apis[:5],  # 너무 길지 않게 일부만 포함
                        'event_id': event.get('EventId'),
                        'event_source': event.get('EventSource')
                    }
                }
                anomalies.append(anomaly)
    
    return anomalies

def detect_time_anomalies(username, events, profile):
    """
    비정상적인 시간 패턴을 탐지합니다.
    
    Args:
        username (str): 사용자명
        events (list): 사용자의 CloudTrail 이벤트 목록
        profile (dict): 사용자 프로파일
        
    Returns:
        list: 시간 관련 이상 행동 목록
    """
    normal_patterns = profile.get('normal_patterns', {})
    active_hours = normal_patterns.get('active_hours', list(range(9, 18)))  # 기본값: 9AM-6PM
    primary_days = normal_patterns.get('primary_days', [0, 1, 2, 3, 4])     # 기본값: 월-금
    
    anomalies = []
    
    for event in events:
        event_time_str = event.get('EventTime')
        if not event_time_str:
            continue
        
        try:
            # ISO 형식 시간 문자열 파싱
            event_time = datetime.datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
            hour = event_time.hour
            day = event_time.weekday()
            
            # 비정상적인 시간에 발생한 이벤트 탐지
            if hour not in active_hours and day not in primary_days:
                # 너무 많은 이상 행동이 생성되지 않도록 제한
                if len(anomalies) < 5:
                    anomaly = {
                        'id': str(uuid.uuid4()),
                        'user_arn': username,
                        'timestamp': int(time.time()),
                        'event_time': event_time_str,
                        'anomaly_type': 'unusual_time',
                        'event_name': event.get('EventName'),
                        'risk_score': 65,  # 비정상 시간은 중간~높은 위험도
                        'details': {
                            'hour': hour,
                            'day': day,
                            'active_hours': active_hours,
                            'primary_days': primary_days,
                            'event_id': event.get('EventId')
                        }
                    }
                    anomalies.append(anomaly)
        except (ValueError, TypeError):
            continue
    
    return anomalies

def detect_privilege_abuse(username, events, profile):
    """
    권한 오용을 탐지합니다.
    
    Args:
        username (str): 사용자명
        events (list): 사용자의 CloudTrail 이벤트 목록
        profile (dict): 사용자 프로파일
        
    Returns:
        list: 권한 오용 관련 이상 행동 목록
    """
    required_permissions = profile.get('required_permissions', [])
    anomalies = []
    
    # 권한 오용 패턴 (특정 서비스에 대한 다양한 API 호출이 짧은 시간에 발생)
    service_api_counts = {}
    
    for event in events:
        event_name = event.get('EventName', '')
        event_source = event.get('EventSource', '')
        
        if event_source.endswith('.amazonaws.com'):
            service = event_source.split('.')[0]
            
            # 서비스별 API 호출 수 증가
            if service not in service_api_counts:
                service_api_counts[service] = set()
            service_api_counts[service].add(event_name)
            
            # 서비스에 대해 다양한 API 호출이 발생한 경우 (5개 이상)
            if len(service_api_counts[service]) >= 5:
                # 비정상적인 서비스 액세스 패턴
                if not any(a.get('anomaly_type') == 'service_sweep' and a.get('service') == service for a in anomalies):
                    anomaly = {
                        'id': str(uuid.uuid4()),
                        'user_arn': username,
                        'timestamp': int(time.time()),
                        'event_time': event.get('EventTime'),
                        'anomaly_type': 'service_sweep',
                        'service': service,
                        'risk_score': 70,  # 서비스 스위핑은 높은 위험도
                        'details': {
                            'api_calls': list(service_api_counts[service]),
                            'event_id': event.get('EventId')
                        }
                    }
                    anomalies.append(anomaly)
    
    return anomalies

def get_user_risk_score(session, user_arn):
    """
    사용자의 위험 점수를 계산합니다.
    
    Args:
        session (boto3.Session): AWS 세션
        user_arn (str): 사용자 ARN
        
    Returns:
        dict: 위험 점수 정보
    """
    # 사용자 프로파일 조회
    profile = get_user_activity_profile(user_arn)
    
    if not profile:
        # 프로파일이 없는 경우 기본 위험 점수 반환
        return {
            'user_arn': user_arn,
            'risk_score': 50,  # 중간 위험도
            'risk_level': 'MEDIUM',
            'last_updated': None,
            'factors': [{
                'type': 'no_profile',
                'score': 50,
                'message': '사용자 행동 프로파일이 없습니다.'
            }]
        }
    
    # 기존 위험 점수 확인
    risk_score = profile.get('risk_score', 50)
    
    # 이상 행동 이벤트 조회
    anomaly_events = get_anomaly_events_by_user(user_arn, limit=10)
    
    # 최근 이상 행동 있으면 위험 점수 증가
    if anomaly_events:
        # 가장 최근 이상 행동의 위험 점수 반영
        recent_anomalies = sorted(anomaly_events, key=lambda x: x.get('timestamp', 0), reverse=True)
        recent_score = recent_anomalies[0].get('risk_score', 50)
        
        # 최근 이상 행동 위험 점수와 프로파일 위험 점수의 가중 평균
        risk_score = int(risk_score * 0.7 + recent_score * 0.3)
    
    # 위험 수준 결정
    if risk_score >= 75:
        risk_level = 'HIGH'
    elif risk_score >= 40:
        risk_level = 'MEDIUM'
    else:
        risk_level = 'LOW'
    
    # 위험 요소 구성
    factors = []
    
    # 권한 수에 따른 요소
    perms_count = len(profile.get('required_permissions', []))
    if perms_count > 50:
        factors.append({
            'type': 'excessive_permissions',
            'count': perms_count,
            'score': 25,
            'message': f'사용자에게 {perms_count}개의 많은 권한이 있습니다.'
        })
    
    # 민감한 서비스 사용에 따른 요소
    service_usage = profile.get('service_usage', {})
    service_counts = service_usage.get('service_counts', {})
    
    sensitive_services = ['iam', 'kms', 'lambda', 'ec2', 's3']
    used_sensitive = [s for s in sensitive_services if s in service_counts]
    
    if used_sensitive:
        factors.append({
            'type': 'sensitive_services',
            'services': used_sensitive,
            'score': 15,
            'message': f'사용자가 {", ".join(used_sensitive)} 등 민감한 서비스를 사용합니다.'
        })
    
    # 최근 이상 행동에 따른 요소
    if anomaly_events:
        factors.append({
            'type': 'recent_anomalies',
            'count': len(anomaly_events),
            'score': 30,
            'message': f'사용자에게 최근 {len(anomaly_events)}개의 이상 행동이 탐지되었습니다.'
        })
    
    # 결과 구성
    return {
        'user_arn': user_arn,
        'risk_score': risk_score,
        'risk_level': risk_level,
        'last_updated': profile.get('last_analyzed'),
        'factors': factors,
        'anomaly_count': len(anomaly_events)
    }