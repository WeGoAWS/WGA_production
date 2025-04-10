# layers/common/utils.py
import json
import boto3
import requests
import logging
from botocore.exceptions import ClientError
from common.config import CONFIG, AWS_REGION

# 로깅 설정
logger = logging.getLogger("wga-utils")
logger.setLevel(logging.INFO)

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
        'claims': event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
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

def invoke_bedrock_nova(prompt):
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
    response = bedrock.invoke_model(
        modelId="amazon.nova-pro-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "inferenceConfig": {
                "max_new_tokens": 1000
            },
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        })
    )
    return json.loads(response["body"].read())