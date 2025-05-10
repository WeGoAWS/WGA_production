import json
import boto3
import os
import uuid
import time
from decimal import Decimal
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key
from common.utils import cors_response

# DynamoDB 리소스 초기화
dynamodb = boto3.resource('dynamodb')
sessions_table_name = os.environ.get('CHAT_SESSIONS_TABLE', '')
messages_table_name = os.environ.get('CHAT_MESSAGES_TABLE', '')

sessions_table = dynamodb.Table(sessions_table_name)
messages_table = dynamodb.Table(messages_table_name)

# TTL 설정 (기본값: 90일)
DEFAULT_TTL_DAYS = int(os.environ.get('DEFAULT_TTL_DAYS', '90'))


def lambda_handler(event, context):
    method = event.get('httpMethod', '')
    path = event.get('path', '')
    origin = event.get('headers', {}).get('origin', '*')

    # OPTIONS 요청 처리 (CORS)
    if method == 'OPTIONS':
        return cors_response(200, {}, origin)

    # 사용자 ID 가져오기 (Cognito 인증 사용 시)
    user_id = get_user_id(event)
    if not user_id:
        return cors_response(401, {"error": "사용자 인증이 필요합니다"}, origin)

    # 요청 경로에 따라 적절한 함수 호출
    try:
        # 세션 목록 가져오기
        if path.endswith('/sessions') and method == 'GET':
            return get_sessions(user_id, event, origin)

        # 새 세션 생성
        elif path.endswith('/sessions') and method == 'POST':
            return create_session(user_id, event, origin)

        # 세션 세부 정보 가져오기
        elif '/sessions/' in path and method == 'GET' and not path.endswith('/messages'):
            session_id = path.split('/')[-1]
            return get_session(user_id, session_id, origin)

        # 세션 업데이트
        elif '/sessions/' in path and method == 'PUT':
            session_id = path.split('/')[-1]
            return update_session(user_id, session_id, event, origin)

        # 세션 삭제
        elif '/sessions/' in path and method == 'DELETE':
            session_id = path.split('/')[-1]
            return delete_session(user_id, session_id, origin)

        # 세션의 메시지 목록 가져오기
        elif path.endswith('/messages') and method == 'GET':
            session_id = path.split('/')[-2]  # /sessions/{sessionId}/messages 패턴에서 추출
            return get_messages(user_id, session_id, event, origin)

        # 메시지 추가
        elif path.endswith('/messages') and method == 'POST':
            session_id = path.split('/')[-2]
            return add_message(user_id, session_id, event, origin)

        # 메시지 삭제
        elif '/messages/' in path and method == 'DELETE':
            session_id = path.split('/')[-3]  # /sessions/{sessionId}/messages/{messageId}
            message_id = path.split('/')[-1]
            return delete_message(user_id, session_id, message_id, origin)

        # 지원하지 않는 경로
        else:
            return cors_response(404, {"error": f"지원하지 않는 경로: {path}"}, origin)

    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return cors_response(500, {"error": f"서버 오류: {str(e)}"}, origin)


def get_user_id(event):
    """
    요청에서 사용자 ID를 추출합니다.
    Cognito 인증이 활성화된 경우 JWT 토큰에서 추출하고,
    그렇지 않은 경우 쿼리 파라미터에서 가져옵니다.
    """
    # Cognito 인증 사용 시
    if 'requestContext' in event and 'authorizer' in event['requestContext']:
        claims = event['requestContext']['authorizer'].get('claims', {})
        # Cognito의 sub 클레임으로 사용자 식별
        return claims.get('sub') or claims.get('cognito:username')

    # 쿼리 파라미터에서 가져오기 (테스트용, 실제 환경에서는 사용하지 않는 것이 좋음)
    query_params = event.get('queryStringParameters', {}) or {}
    if 'userId' in query_params:
        return query_params['userId']

    # Request body에서 가져오기
    try:
        body = json.loads(event.get('body', '{}'))
        if 'userId' in body:
            return body['userId']
    except:
        pass

    return None


def generate_ttl(days=DEFAULT_TTL_DAYS):
    """지정된 일수 후의 TTL 타임스탬프를 생성합니다."""
    return int((datetime.now() + timedelta(days=days)).timestamp())


def get_sessions(user_id, event, origin):
    """사용자의 채팅 세션 목록을 반환합니다."""
    query_params = event.get('queryStringParameters', {}) or {}
    limit = int(query_params.get('limit', '20'))

    # 'userId-createdAt-index' GSI를 사용하여 최신 세션부터 정렬
    response = sessions_table.query(
        IndexName='CreatedAtIndex',
        KeyConditionExpression=Key('userId').eq(user_id),
        ScanIndexForward=False,  # 내림차순 (최신순)
        Limit=limit
    )

    sessions = response.get('Items', [])

    # DynamoDB Decimal 타입 변환 (JSON 직렬화를 위해)
    for session in sessions:
        for key, value in session.items():
            if isinstance(value, Decimal):
                session[key] = float(value)

    return cors_response(200, {"sessions": sessions}, origin)


def create_session(user_id, event, origin):
    """새 채팅 세션을 생성합니다."""
    try:
        body = json.loads(event.get('body', '{}'))
    except:
        return cors_response(400, {"error": "잘못된 요청 본문"}, origin)

    session_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    # 기본 제목 설정 (없는 경우)
    title = body.get('title', f'새 대화 {timestamp.split("T")[0]}')

    session_item = {
        'userId': user_id,
        'sessionId': session_id,
        'title': title,
        'createdAt': timestamp,
        'updatedAt': timestamp,
        'messageCount': 0,
        'ttl': generate_ttl()
    }

    sessions_table.put_item(Item=session_item)

    return cors_response(201, {"session": session_item}, origin)


def get_session(user_id, session_id, origin):
    """세션 세부 정보를 가져옵니다."""
    response = sessions_table.get_item(
        Key={
            'userId': user_id,
            'sessionId': session_id
        }
    )

    session = response.get('Item')
    if not session:
        return cors_response(404, {"error": "세션을 찾을 수 없음"}, origin)

    # DynamoDB Decimal 타입 변환
    for key, value in session.items():
        if isinstance(value, Decimal):
            session[key] = float(value)

    return cors_response(200, {"session": session}, origin)


def update_session(user_id, session_id, event, origin):
    """세션 정보를 업데이트합니다."""
    try:
        body = json.loads(event.get('body', '{}'))
    except:
        return cors_response(400, {"error": "잘못된 요청 본문"}, origin)

    # 세션이 존재하는지 확인
    response = sessions_table.get_item(
        Key={
            'userId': user_id,
            'sessionId': session_id
        }
    )

    if not response.get('Item'):
        return cors_response(404, {"error": "세션을 찾을 수 없음"}, origin)

    update_expression = "SET updatedAt = :updatedAt"
    expression_values = {
        ":updatedAt": datetime.now().isoformat()
    }

    # 업데이트 가능한 필드
    updatable_fields = ['title']

    for field in updatable_fields:
        if field in body:
            update_expression += f", {field} = :{field}"
            expression_values[f":{field}"] = body[field]

    # TTL 업데이트 (활동이 있으면 TTL 연장)
    update_expression += ", ttl = :ttl"
    expression_values[":ttl"] = generate_ttl()

    sessions_table.update_item(
        Key={
            'userId': user_id,
            'sessionId': session_id
        },
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values,
        ReturnValues="ALL_NEW"
    )

    return cors_response(200, {"message": "세션이 업데이트됨"}, origin)


def delete_session(user_id, session_id, origin):
    """세션과 관련 메시지를 삭제합니다."""
    # 세션이 존재하는지 확인
    response = sessions_table.get_item(
        Key={
            'userId': user_id,
            'sessionId': session_id
        }
    )

    if not response.get('Item'):
        return cors_response(404, {"error": "세션을 찾을 수 없음"}, origin)

    # 세션 삭제
    sessions_table.delete_item(
        Key={
            'userId': user_id,
            'sessionId': session_id
        }
    )

    # 관련 메시지 삭제 (배치 처리)
    message_response = messages_table.query(
        KeyConditionExpression=Key('sessionId').eq(session_id)
    )

    messages = message_response.get('Items', [])

    # 메시지가 있는 경우 배치 삭제
    if messages:
        with messages_table.batch_writer() as batch:
            for message in messages:
                batch.delete_item(
                    Key={
                        'sessionId': session_id,
                        'messageId': message['messageId']
                    }
                )

    return cors_response(200, {"message": "세션과 관련 메시지가 삭제됨"}, origin)


def get_messages(user_id, session_id, event, origin):
    """세션의 메시지 목록을 가져옵니다."""
    # 세션이 존재하고 사용자의 세션인지 확인
    session_response = sessions_table.get_item(
        Key={
            'userId': user_id,
            'sessionId': session_id
        }
    )

    if not session_response.get('Item'):
        return cors_response(404, {"error": "세션을 찾을 수 없음"}, origin)

    # 메시지 쿼리
    message_response = messages_table.query(
        IndexName='TimestampIndex',
        KeyConditionExpression=Key('sessionId').eq(session_id),
        ScanIndexForward=True  # 오름차순 (시간순)
    )

    messages = message_response.get('Items', [])

    # DynamoDB Decimal 타입 변환
    for message in messages:
        for key, value in message.items():
            if isinstance(value, Decimal):
                message[key] = float(value)

    return cors_response(200, {"messages": messages}, origin)


def add_message(user_id, session_id, event, origin):
    """세션에 새 메시지를 추가합니다."""
    try:
        body = json.loads(event.get('body', '{}'))
    except:
        return cors_response(400, {"error": "잘못된 요청 본문"}, origin)

    # 세션이 존재하고 사용자의 세션인지 확인
    session_response = sessions_table.get_item(
        Key={
            'userId': user_id,
            'sessionId': session_id
        }
    )

    if not session_response.get('Item'):
        return cors_response(404, {"error": "세션을 찾을 수 없음"}, origin)

    session = session_response['Item']

    # 필수 필드 확인
    if 'text' not in body or 'sender' not in body:
        return cors_response(400, {"error": "text와 sender는 필수 필드입니다"}, origin)

    message_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    message_item = {
        'sessionId': session_id,
        'messageId': message_id,
        'text': body['text'],
        'sender': body['sender'],  # 'user' 또는 'bot'
        'timestamp': timestamp,
        'ttl': generate_ttl()
    }

    # 추가 필드가 있는 경우
    for key in ['displayText', 'isTyping', 'animationState']:
        if key in body:
            message_item[key] = body[key]

    # 메시지 저장
    messages_table.put_item(Item=message_item)

    # 세션 업데이트 (메시지 수 증가 및 마지막 업데이트 시간)
    sessions_table.update_item(
        Key={
            'userId': user_id,
            'sessionId': session_id
        },
        UpdateExpression="SET messageCount = if_not_exists(messageCount, :zero) + :increment, updatedAt = :updatedAt, ttl = :ttl",
        ExpressionAttributeValues={
            ":increment": 1,
            ":zero": 0,
            ":updatedAt": timestamp,
            ":ttl": generate_ttl()
        }
    )

    return cors_response(201, {"message": message_item}, origin)


def delete_message(user_id, session_id, message_id, origin):
    """메시지를 삭제합니다."""
    # 세션이 존재하고 사용자의 세션인지 확인
    session_response = sessions_table.get_item(
        Key={
            'userId': user_id,
            'sessionId': session_id
        }
    )

    if not session_response.get('Item'):
        return cors_response(404, {"error": "세션을 찾을 수 없음"}, origin)

    # 메시지 존재 확인
    message_response = messages_table.get_item(
        Key={
            'sessionId': session_id,
            'messageId': message_id
        }
    )

    if not message_response.get('Item'):
        return cors_response(404, {"error": "메시지를 찾을 수 없음"}, origin)

    # 메시지 삭제
    messages_table.delete_item(
        Key={
            'sessionId': session_id,
            'messageId': message_id
        }
    )

    # 세션 업데이트 (메시지 수 감소)
    sessions_table.update_item(
        Key={
            'userId': user_id,
            'sessionId': session_id
        },
        UpdateExpression="SET messageCount = if_not_exists(messageCount, :zero) - :decrement, updatedAt = :updatedAt",
        ExpressionAttributeValues={
            ":decrement": 1,
            ":zero": 1,  # 마이너스가 되지 않도록
            ":updatedAt": datetime.now().isoformat()
        },
        ConditionExpression="messageCount > :zero"
    )

    return cors_response(200, {"message": "메시지가 삭제됨"}, origin)