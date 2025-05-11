import boto3
import uuid
import datetime
from boto3.dynamodb.conditions import Key
from common.config import get_config
from common.utils import cors_response

# 설정 로드
CONFIG = get_config()
CHAT_HISTORY_TABLE = CONFIG['db']['chat_history_table']

# DynamoDB 리소스 초기화
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(CHAT_HISTORY_TABLE)

# KST 타임존 정의
KST = datetime.timezone(datetime.timedelta(hours=9))

def handle_chat_history_request(path, http_method, body, event, origin):
    """채팅 기록 관련 요청 처리"""

    # /sessions 엔드포인트 처리
    if path.endswith('/sessions'):
        if http_method == "OPTIONS":
            response = cors_response(200, "", origin)
            return response
        elif http_method == 'POST':
            # 새 세션 생성
            result = create_session(body)
            return cors_response(200, result, origin)

        elif http_method == 'GET':
            # 사용자의 세션 목록 조회
            query_params = event.get('queryStringParameters', {}) or {}
            user_id = query_params.get('userId')

            if not user_id:
                return cors_response(400, {'error': 'Missing userId parameter'}, origin)

            sessions = get_sessions(user_id)
            return cors_response(200, {'sessions': sessions}, origin)

    # 세션 ID 파싱 (정규식 대신 간단한 방법 사용)
    path_parts = path.split('/')
    session_id = None

    # /sessions/{sessionId} 패턴 확인
    for i, part in enumerate(path_parts):
        if part == 'sessions' and i + 1 < len(path_parts):
            session_id = path_parts[i + 1]
            break

    if not session_id:
        return cors_response(400, {'error': 'Invalid path'}, origin)

    # 세션 ID가 유효한 경우 요청 처리
    if path.endswith(f'/sessions/{session_id}'):
        if http_method == "OPTIONS":
            response = cors_response(200, "", origin)
            return response
        # 특정 세션 관련 요청
        elif http_method == 'GET':
            # 세션 조회
            session = get_session(session_id)
            if not session:
                return cors_response(404, {'error': 'Session not found'}, origin)
            return cors_response(200, session, origin)

        elif http_method == 'PUT':
            # 세션 업데이트
            title = body.get('title')
            if not title:
                return cors_response(400, {'error': 'title is required'}, origin)

            updated_session = update_session(session_id, title)
            if not updated_session:
                return cors_response(404, {'error': 'Session not found'}, origin)

            return cors_response(200, updated_session, origin)

        elif http_method == 'DELETE':
            # 세션 삭제
            success = delete_session(session_id)
            if not success:
                return cors_response(404, {'error': 'Session not found'}, origin)

            return cors_response(200, {'message': 'Session deleted successfully'}, origin)

    # /sessions/{sessionId}/messages 패턴 확인
    elif path.endswith(f'/sessions/{session_id}/messages'):
        if http_method == "OPTIONS":
            response = cors_response(200, "", origin)
            return response
        elif http_method == 'GET':
            # 메시지 목록 조회
            messages = get_messages(session_id)
            if messages is None:
                return cors_response(404, {'error': 'Session not found'}, origin)

            return cors_response(200, {'messages': messages}, origin)

        elif http_method == 'POST':
            # 메시지 추가
            sender = body.get('sender')
            text = body.get('text')

            if not sender or not text:
                return cors_response(400, {'error': 'sender and text are required'}, origin)

            message = add_message(session_id, sender, text)
            if not message:
                return cors_response(404, {'error': 'Session not found'}, origin)

            return cors_response(200, message, origin)

    # 지원하지 않는 경로
    return cors_response(404, {'error': f'Route not found: {http_method} {path}'}, origin)


def create_session(data):
    """새로운 채팅 세션 생성"""
    user_id = data.get('userId', str(uuid.uuid4()))
    title = data.get('title', '새 대화')

    session_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now(KST).isoformat()

    # DynamoDB에 세션 정보 저장
    session_item = {
        'sessionId': session_id,
        'userId': user_id,
        'title': title,
        'createdAt': timestamp,
        'updatedAt': timestamp,
        'messages': []
    }

    table.put_item(Item=session_item)

    # 메시지 필드 제외한 결과 반환
    return {
        'sessionId': session_id,
        'userId': user_id,
        'title': title,
        'createdAt': timestamp,
        'updatedAt': timestamp
    }


def get_sessions(user_id):
    """사용자 ID에 해당하는, 모든 채팅 세션 조회"""
    # 사용자 ID에 해당하는 세션 조회 (GlobalSecondaryIndex 사용)
    response = table.query(
        IndexName='UserIdIndex',
        KeyConditionExpression=Key('userId').eq(user_id)
    )

    sessions = []
    for item in response.get('Items', []):
        # 메시지 필드는 응답에서 제외 (크기 절약)
        if 'messages' in item:
            del item['messages']
        sessions.append(item)

    # 업데이트 시간 기준 내림차순 정렬
    sessions.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)

    return sessions


def get_session(session_id):
    """세션 ID에 해당하는 세션 정보 조회"""
    response = table.get_item(
        Key={'sessionId': session_id}
    )

    session = response.get('Item')
    if not session:
        return None

    # 메시지 필드는 응답에서 제외 (별도 API로 조회)
    if 'messages' in session:
        del session['messages']

    return session


def update_session(session_id, title):
    """세션 ID에 해당하는 세션 정보 업데이트"""
    # 세션 정보 조회
    response = table.get_item(
        Key={'sessionId': session_id}
    )

    session = response.get('Item')
    if not session:
        return None

    # 세션 정보 업데이트
    timestamp = datetime.datetime.now(KST).isoformat()

    update_expression = "SET title = :title, updatedAt = :updatedAt"
    expression_values = {
        ':title': title,
        ':updatedAt': timestamp
    }

    table.update_item(
        Key={'sessionId': session_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values
    )

    # 업데이트된 세션 정보 반환
    return {
        'sessionId': session_id,
        'title': title,
        'updatedAt': timestamp
    }


def delete_session(session_id):
    """세션 ID에 해당하는 세션 삭제"""
    # 세션 정보 조회
    response = table.get_item(
        Key={'sessionId': session_id}
    )

    session = response.get('Item')
    if not session:
        return False

    # 세션 삭제
    table.delete_item(
        Key={'sessionId': session_id}
    )

    return True


def add_message(session_id, sender, text):
    """세션에 새 메시지 추가"""
    # 세션 정보 조회
    response = table.get_item(
        Key={'sessionId': session_id}
    )

    session = response.get('Item')
    if not session:
        return None

    # 새 메시지 생성
    message_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now(KST).isoformat()

    message = {
        'id': message_id,
        'sender': sender,
        'text': text,
        'timestamp': timestamp
    }

    # 메시지 추가 및 세션 업데이트 시간 변경
    messages = session.get('messages', [])
    messages.append(message)

    table.update_item(
        Key={'sessionId': session_id},
        UpdateExpression="SET messages = :messages, updatedAt = :updatedAt",
        ExpressionAttributeValues={
            ':messages': messages,
            ':updatedAt': timestamp
        }
    )

    return message


def get_messages(session_id):
    """세션의 모든 메시지 조회"""
    # 세션 정보 조회
    response = table.get_item(
        Key={'sessionId': session_id}
    )

    session = response.get('Item')
    if not session:
        return None

    # 메시지 반환
    return session.get('messages', [])