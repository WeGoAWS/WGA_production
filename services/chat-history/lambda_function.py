# services/chat-history/lambda_function.py
import json
import boto3
import uuid
import os
import datetime
from urllib.parse import parse_qs
from common.utils import cors_response

# 환경 변수에서 값 가져오기
CHAT_HISTORY_TABLE = os.environ.get('CHAT_HISTORY_TABLE', 'wga-chat-history-dev')
ENV = os.environ.get('ENV', 'dev')

# DynamoDB 리소스 초기화
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(CHAT_HISTORY_TABLE)


def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")

    # CORS 처리를 위한 origin 설정
    origin = event.get('headers', {}).get('origin', f"https://{ENV}.amplifyapp.com")

    # OPTIONS 요청 처리 (CORS preflight)
    if event.get('httpMethod') == 'OPTIONS':
        return cors_response(200, {}, origin)

    # 경로 및 메서드에 따른 핸들러 함수 호출
    try:
        path = event.get('path', '')
        http_method = event.get('httpMethod', '')

        # /sessions 경로 처리
        if path.endswith('/sessions') and http_method == 'POST':
            return create_session(event, origin)
        elif path.endswith('/sessions') and http_method == 'GET':
            return get_sessions(event, origin)

        # /sessions/{sessionId} 경로 처리
        elif '/sessions/' in path and not path.endswith('/messages'):
            session_id = event['pathParameters']['sessionId']

            if http_method == 'GET':
                return get_session(session_id, origin)
            elif http_method == 'PUT':
                return update_session(session_id, event, origin)
            elif http_method == 'DELETE':
                return delete_session(session_id, origin)

        # /sessions/{sessionId}/messages 경로 처리
        elif '/messages' in path:
            session_id = event['pathParameters']['sessionId']

            if http_method == 'POST':
                return add_message(session_id, event, origin)
            elif http_method == 'GET':
                return get_messages(session_id, origin)

        # 알 수 없는 경로
        return cors_response(404, {'error': f'Route not found: {http_method} {path}'}, origin)

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return cors_response(500, {'error': str(e)}, origin)


def parse_body(event):
    """이벤트에서 본문 파싱"""
    body = event.get('body', '{}')

    content_type = event.get('headers', {}).get('content-type', '')
    if 'application/json' in content_type:
        return json.loads(body)
    elif 'application/x-www-form-urlencoded' in content_type:
        return {k: v[0] for k, v in parse_qs(body).items()}
    else:
        try:
            return json.loads(body)
        except:
            return {}


def create_session(event, origin):
    """새로운 채팅 세션 생성"""
    try:
        body = parse_body(event)
        user_id = body.get('userId', str(uuid.uuid4()))
        title = body.get('title', '새 대화')

        session_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()

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

        return cors_response(200, {
            'sessionId': session_id,
            'userId': user_id,
            'title': title,
            'createdAt': timestamp,
            'updatedAt': timestamp
        }, origin)

    except Exception as e:
        print(f"Error creating session: {str(e)}")
        return cors_response(500, {'error': str(e)}, origin)


def get_sessions(event, origin):
    """사용자 ID에 해당하는, 모든 채팅 세션 조회"""
    try:
        # 쿼리 파라미터에서 사용자 ID 추출
        query_params = event.get('queryStringParameters', {}) or {}
        user_id = query_params.get('userId')

        if not user_id:
            return cors_response(400, {'error': 'Missing userId parameter'}, origin)

        # 사용자 ID에 해당하는 세션 조회 (GlobalSecondaryIndex 사용)
        response = table.query(
            IndexName='UserIdIndex',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('userId').eq(user_id)
        )

        sessions = []
        for item in response.get('Items', []):
            # 메시지 필드는 응답에서 제외 (크기 절약)
            if 'messages' in item:
                del item['messages']
            sessions.append(item)

        # 업데이트 시간 기준 내림차순 정렬
        sessions.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)

        return cors_response(200, {'sessions': sessions}, origin)

    except Exception as e:
        print(f"Error getting sessions: {str(e)}")
        return cors_response(500, {'error': str(e)}, origin)


def get_session(session_id, origin):
    """세션 ID에 해당하는 세션 정보 조회"""
    try:
        response = table.get_item(
            Key={'sessionId': session_id}
        )

        session = response.get('Item')
        if not session:
            return cors_response(404, {'error': 'Session not found'}, origin)

        # 메시지 필드는 응답에서 제외 (별도 API로 조회)
        if 'messages' in session:
            del session['messages']

        return cors_response(200, session, origin)

    except Exception as e:
        print(f"Error getting session: {str(e)}")
        return cors_response(500, {'error': str(e)}, origin)


def update_session(session_id, event, origin):
    """세션 ID에 해당하는 세션 정보 업데이트"""
    try:
        body = parse_body(event)
        title = body.get('title')

        if not title:
            return cors_response(400, {'error': 'title is required'}, origin)

        # 세션 정보 조회
        response = table.get_item(
            Key={'sessionId': session_id}
        )

        session = response.get('Item')
        if not session:
            return cors_response(404, {'error': 'Session not found'}, origin)

        # 세션 정보 업데이트
        timestamp = datetime.datetime.now().isoformat()

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
        return cors_response(200, {
            'sessionId': session_id,
            'title': title,
            'updatedAt': timestamp
        }, origin)

    except Exception as e:
        print(f"Error updating session: {str(e)}")
        return cors_response(500, {'error': str(e)}, origin)


def delete_session(session_id, origin):
    """세션 ID에 해당하는 세션 삭제"""
    try:
        # 세션 정보 조회
        response = table.get_item(
            Key={'sessionId': session_id}
        )

        session = response.get('Item')
        if not session:
            return cors_response(404, {'error': 'Session not found'}, origin)

        # 세션 삭제
        table.delete_item(
            Key={'sessionId': session_id}
        )

        return cors_response(200, {'message': 'Session deleted successfully'}, origin)

    except Exception as e:
        print(f"Error deleting session: {str(e)}")
        return cors_response(500, {'error': str(e)}, origin)


def add_message(session_id, event, origin):
    """세션에 새 메시지 추가"""
    try:
        body = parse_body(event)

        sender = body.get('sender')
        text = body.get('text')

        if not sender or not text:
            return cors_response(400, {'error': 'sender and text are required'}, origin)

        # 세션 정보 조회
        response = table.get_item(
            Key={'sessionId': session_id}
        )

        session = response.get('Item')
        if not session:
            return cors_response(404, {'error': 'Session not found'}, origin)

        # 새 메시지 생성
        message_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()

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

        return cors_response(200, message, origin)

    except Exception as e:
        print(f"Error adding message: {str(e)}")
        return cors_response(500, {'error': str(e)}, origin)


def get_messages(session_id, origin):
    """세션의 모든 메시지 조회"""
    try:
        # 세션 정보 조회
        response = table.get_item(
            Key={'sessionId': session_id}
        )

        session = response.get('Item')
        if not session:
            return cors_response(404, {'error': 'Session not found'}, origin)

        # 메시지 반환
        messages = session.get('messages', [])

        return cors_response(200, {'messages': messages}, origin)

    except Exception as e:
        print(f"Error getting messages: {str(e)}")
        return cors_response(500, {'error': str(e)}, origin)