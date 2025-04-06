# layers/common/utils.py
import json
import boto3
import time
import datetime
import logging
from botocore.exceptions import ClientError
from common.config import CONFIG
from common.db import get_session

# 로깅 설정
logger = logging.getLogger("wga-utils")
logger.setLevel(logging.INFO)

def extract_session_id_from_cookies(cookies_string):
    """
    쿠키 문자열에서 세션 ID를 추출합니다.
    
    Args:
        cookies_string (str): 쿠키 문자열
        
    Returns:
        str: 세션 ID 또는 None
    """
    if not cookies_string:
        return None
    
    cookies = {}
    for cookie in cookies_string.split(';'):
        if '=' in cookie:
            name, value = cookie.strip().split('=', 1)
            cookies[name] = value
    
    return cookies.get('session')

def get_id_token_from_session(event):
    """
    요청의 세션 쿠키에서 ID 토큰을 추출합니다.
    중앙화된 함수로, 모든 람다 핸들러에서 공통으로 사용합니다.
    
    Args:
        event (dict): API Gateway 이벤트
        
    Returns:
        str: ID 토큰 또는 None
    """
    # 쿠키에서 세션 ID 추출
    headers = event.get('headers', {})
    cookies = headers.get('Cookie', '') or headers.get('cookie', '')
    
    session_id = extract_session_id_from_cookies(cookies)
    
    if not session_id:
        return None
    
    # 세션 정보 조회
    session = get_session(session_id)
    
    # 세션에서 ID 토큰 반환
    id_token = session.get('id_token') if session else None
    
    return id_token

def format_api_response(status_code, body, headers=None):
    """
    API Gateway 응답을 포맷팅합니다.
    
    Args:
        status_code (int): HTTP 상태 코드
        body (dict/list/str): 응답 본문
        headers (dict, optional): 추가 헤더
        
    Returns:
        dict: API Gateway 응답 객체
    """
    # 기본 Content-Type 헤더 설정
    default_headers = {
        'Content-Type': 'application/json; charset=utf-8',
    }
    
    # CORS 헤더 추가
    default_headers.update(get_cors_headers())
    
    # 사용자 정의 헤더 추가
    if headers:
        default_headers.update(headers)
    
    response = {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body, ensure_ascii=False) if isinstance(body, (dict, list)) else str(body)
    }
    return response

def handle_api_exception(e, status_code=500):
    """
    API 예외를 처리합니다.
    
    Args:
        e (Exception): 예외 객체
        status_code (int): HTTP 상태 코드
        
    Returns:
        dict: API Gateway 응답 객체
    """
    error_message = str(e)
    logger.error(f"API 오류: {error_message}", exc_info=True)
    
    return format_api_response(
        status_code,
        {'error': error_message}
    )

def get_aws_session(id_token):
    """
    ID 토큰을 사용하여 AWS 임시 세션을 생성합니다.
    
    Args:
        id_token (str): Cognito ID 토큰
        
    Returns:
        boto3.Session: AWS 세션 객체
    """
    cognito_domain = CONFIG['cognito']['domain']
    cognito_identity_pool_id = CONFIG['cognito']['identity_pool_id']
    
    login_provider = cognito_domain.removeprefix("https://")
    cognito_identity = boto3.client("cognito-identity", region_name=CONFIG['aws_region'])
    
    try:
        # Cognito ID 얻기
        identity_response = cognito_identity.get_id(
            IdentityPoolId=cognito_identity_pool_id,
            Logins={login_provider: id_token}
        )
        identity_id = identity_response.get("IdentityId")
        
        # 임시 자격 증명 얻기
        credentials_response = cognito_identity.get_credentials_for_identity(
            IdentityId=identity_id,
            Logins={login_provider: id_token}
        )
        creds = credentials_response.get("Credentials")
        
        if not creds:
            raise Exception("Failed to obtain temporary credentials.")
        
        # datetime 객체를 ISO 포맷 문자열로 변환
        if "Expiration" in creds and hasattr(creds["Expiration"], "isoformat"):
            creds["Expiration"] = creds["Expiration"].isoformat()
        
        # AWS 세션 생성
        session = boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretKey"],
            aws_session_token=creds["SessionToken"],
            region_name=CONFIG['aws_region'],
        )
        return session
    except Exception as e:
        logger.error(f"Error creating AWS session: {e}", exc_info=True)
        raise

def upload_to_s3(session, bucket, key, data):
    """
    S3 버킷에 데이터를 업로드합니다.
    
    Args:
        session (boto3.Session): AWS 세션
        bucket (str): S3 버킷 이름
        key (str): 객체 키
        data: 업로드할 데이터 (문자열, 바이트, 딕셔너리, 리스트)
        
    Returns:
        bool: 성공 여부
    """
    try:
        s3_client = session.client('s3')
        
        # 문자열 또는 딕셔너리/리스트인 경우 JSON 문자열로 변환
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False)
        
        # 파일 객체가 아닌 바이트 또는 문자열 데이터 처리
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data
        )
        return True
    except ClientError as e:
        logger.error(f"Error uploading to S3: {e.response['Error']['Message']}", exc_info=True)
        return False

def download_from_s3(session, bucket, key, encoding=None):
    """
    S3 버킷에서 객체를 다운로드합니다.
    
    Args:
        session (boto3.Session): AWS 세션
        bucket (str): S3 버킷 이름
        key (str): 객체 키
        encoding (str, optional): 인코딩 (지정 시 문자열로 반환)
        
    Returns:
        bytes/str: 다운로드한 객체 (바이트 또는 문자열)
    """
    try:
        s3_client = session.client('s3')
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = response['Body'].read()
        
        # 인코딩이 지정된 경우 문자열로 디코딩
        if encoding:
            return data.decode(encoding)
        return data
    except ClientError as e:
        logger.error(f"Error downloading from S3: {e.response['Error']['Message']}", exc_info=True)
        return None

def get_latest_s3_object(session, bucket, prefix=''):
    """
    S3 버킷에서 지정된 접두사로 시작하는 최신 객체의 키를 가져옵니다.
    
    Args:
        session (boto3.Session): AWS 세션
        bucket (str): S3 버킷 이름
        prefix (str): 객체 접두사
        
    Returns:
        str: 최신 객체 키 또는 None
    """
    try:
        s3_client = session.client('s3')
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix
        )
        
        if 'Contents' not in response or not response['Contents']:
            return None
        
        # LastModified 기준으로 정렬하여 최신 파일 찾기
        latest_file = max(response['Contents'], key=lambda x: x['LastModified'])
        return latest_file['Key']
    except ClientError as e:
        logger.error(f"Error listing S3 objects: {e.response['Error']['Message']}", exc_info=True)
        return None

def invoke_lambda(session, function_name, payload, invocation_type='RequestResponse'):
    """
    다른 Lambda 함수를 호출합니다.
    
    Args:
        session (boto3.Session): AWS 세션
        function_name (str): 호출할 함수 이름
        payload (dict): 전달할 페이로드
        invocation_type (str): 호출 유형 (RequestResponse, Event)
        
    Returns:
        dict: 호출 응답 또는 None
    """
    try:
        lambda_client = session.client('lambda')
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType=invocation_type,
            Payload=json.dumps(payload)
        )
        
        # 동기 호출인 경우 결과 반환
        if invocation_type == 'RequestResponse' and 'Payload' in response:
            return json.loads(response['Payload'].read())
        
        return {'StatusCode': response.get('StatusCode')}
    except ClientError as e:
        logger.error(f"Error invoking Lambda: {e.response['Error']['Message']}", exc_info=True)
        return None

def publish_to_sns(session, topic_arn, message, subject=None, attributes=None):
    """
    SNS 토픽에 메시지를 발행합니다.
    
    Args:
        session (boto3.Session): AWS 세션
        topic_arn (str): SNS 토픽 ARN
        message (str/dict): 발행할 메시지
        subject (str, optional): 메시지 제목
        attributes (dict, optional): 메시지 속성
        
    Returns:
        bool: 성공 여부
    """
    try:
        sns_client = session.client('sns')
        
        # 메시지가 딕셔너리인 경우 JSON 문자열로 변환
        if isinstance(message, dict):
            message = json.dumps(message)
        
        params = {
            'TopicArn': topic_arn,
            'Message': message
        }
        
        if subject:
            params['Subject'] = subject
        
        if attributes:
            params['MessageAttributes'] = attributes
        
        sns_client.publish(**params)
        return True
    except ClientError as e:
        logger.error(f"Error publishing to SNS: {e.response['Error']['Message']}", exc_info=True)
        return False

def get_active_cloudtrail_s3_buckets(session):
    """
    CloudTrail이 활성화된 S3 버킷 목록을 가져옵니다.
    
    Args:
        session (boto3.Session): AWS 세션
        
    Returns:
        list: S3 버킷 이름 목록
    """
    try:
        cloudtrail_client = session.client("cloudtrail")
        trails = cloudtrail_client.describe_trails().get("trailList", [])
        
        active_buckets = []
        for trail in trails:
            s3_bucket = trail.get("S3BucketName")
            if s3_bucket:
                try:
                    # 각 트레일의 상태를 확인하여 로깅이 활성화되어 있는지 체크
                    status = cloudtrail_client.get_trail_status(Name=trail.get("Name"))
                    if status.get("IsLogging"):
                        active_buckets.append(s3_bucket)
                except Exception as e:
                    logger.warning(f"트레일 상태 조회 실패: {trail.get('Name')} - {e}")
                    continue
        
        return active_buckets
    except ClientError as e:
        logger.error(f"CloudTrail access error: {e.response['Error']['Message']}", exc_info=True)
        raise

def validate_request_parameters(params, required_params):
    """
    요청 파라미터의 유효성을 검사합니다.
    
    Args:
        params (dict): 요청 파라미터
        required_params (list): 필수 파라미터 목록
        
    Returns:
        tuple: (유효성 여부, 오류 메시지)
    """
    missing_params = []
    
    for param in required_params:
        if param not in params or params[param] is None or params[param] == '':
            missing_params.append(param)
    
    if missing_params:
        return False, f"필수 파라미터가 누락되었습니다: {', '.join(missing_params)}"
    
    return True, None

def normalize_event(event):
    """
    API Gateway 이벤트를 정규화합니다.
    
    Args:
        event (dict): API Gateway 이벤트
        
    Returns:
        dict: 정규화된 이벤트
    """
    # 쿼리 파라미터 처리
    query_params = event.get('queryStringParameters', {}) or {}
    
    # 요청 바디 처리
    body = None
    if 'body' in event and event['body']:
        try:
            body = json.loads(event['body'])
        except (json.JSONDecodeError, TypeError):
            body = event['body']
    
    # 정규화된 이벤트 생성
    normalized_event = {
        'path': event.get('path', '/'),
        'httpMethod': event.get('httpMethod', 'GET'),
        'queryParameters': query_params,
        'body': body,
        'headers': event.get('headers', {}),
        'requestContext': event.get('requestContext', {}),
        'id_token': get_id_token_from_session(event)
    }
    
    return normalized_event

def create_error_response(message, status_code=400):
    """
    오류 응답을 생성합니다.
    
    Args:
        message (str): 오류 메시지
        status_code (int): HTTP 상태 코드
        
    Returns:
        dict: API Gateway 응답 객체
    """
    return format_api_response(
        status_code, 
        {"error": True, "message": message}
    )

def create_success_response(data=None, message=None):
    """
    성공 응답을 생성합니다.
    
    Args:
        data: 응답 데이터
        message (str, optional): 성공 메시지
        
    Returns:
        dict: API Gateway 응답 객체
    """
    response_body = {"success": True}
    
    if data is not None:
        response_body["data"] = data
    
    if message:
        response_body["message"] = message
    
    return format_api_response(200, response_body)

def get_cors_headers():
    """
    CONFIG에서 CORS 설정을 기반으로 헤더를 반환합니다.

    Returns:
        dict: CORS 헤더 딕셔너리
    """
    cors = CONFIG.get("cors", {})
    origin = cors.get("allowed_origins", ["http://localhost:5173"])[0]
    methods = ",".join(cors.get("allowed_methods", ["GET", "POST", "PUT", "DELETE", "OPTIONS"]))
    headers = ",".join(cors.get("allowed_headers", ["Content-Type", "Authorization"]))
    allow_credentials = cors.get("allow_credentials", True)

    return {
        'Access-Control-Allow-Origin': origin,
        'Access-Control-Allow-Headers': headers,
        'Access-Control-Allow-Methods': methods,
        'Access-Control-Allow-Credentials': str(allow_credentials).lower()
    }