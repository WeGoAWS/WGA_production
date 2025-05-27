from common.slackbot_session import get_session
from slack_sdk import WebClient
from common.config import get_config
import requests
import json
import boto3
import time

print("==== Lambda 호출됨 ====")

CONFIG = get_config()
client = WebClient(token=CONFIG["slackbot"]["token"])
dynamodb = boto3.resource('dynamodb')
user_settings_table = dynamodb.Table('slack_user_settings')

def send_login_button(slack_user_id):
    login_url = (
        f"{CONFIG['cognito']['domain']}/oauth2/authorize"
        "?response_type=code"
        f"&client_id={CONFIG['cognito']['client_id']}"
        f"&redirect_uri={CONFIG['api']['endpoint']}/callback"
        f"&scope=openid+email+profile&state={slack_user_id}"
    )

    client.chat_postMessage(
        channel=slack_user_id,
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "🔐 AWS 로그인을 위해 아래 버튼을 클릭하세요."}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "로그인"},
                        "url": login_url
                    }
                ]
            }
        ]
    )

def get_models_from_api():
    """
    API에서 모델 목록을 가져오는 함수
    """
    try:
        res = requests.get(
            f"{CONFIG['api']['endpoint']}/health",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        print(f"res: {res}\n")
        
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "ok" and "models" in data:
                return data["models"]
        
        return get_default_models()
        
    except Exception as e:
        print(f"Error fetching models from API: {e}")
        return get_default_models()

def get_default_models():
    """
    API 호출 실패 시 사용할 기본 모델 목록
    """
    return [
        {"id": "claude-3-7-sonnet-20250219", "display_name": "Claude Sonnet 3.7"}
    ]

def convert_to_slack_options(models):
    """
    API 응답을 Slack Block Kit 옵션 형태로 변환
    """
    options = []
    for model in models:
        options.append({
            "text": {
                "type": "plain_text",
                "text": model["display_name"]
            },
            "value": model["id"]
        })
    print(f"options: {options}\n")
    return options

def handle_models_command(slack_user_id):
    """
    /models 명령어 처리 - 모델 선택 드롭다운과 적용 버튼 제공
    """
    print("get_models_from_api 함수 실행\n")
    models = get_models_from_api()
    print(f"models: {models}\n")
    print("convert_to_slack_options 함수 실행\n")
    available_models = convert_to_slack_options(models)
    print(f"available_models: {available_models}\n")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "🤖 *AI 모델을 선택하세요*\n선택한 모델은 `/req` 명령어에서 사용됩니다."
            }
        },
        {
            "type": "section",
            "block_id": "model_selection_block",  # block_id는 여기에만
            "text": {
                "type": "mrkdwn",
                "text": "사용할 모델:"
            },
            "accessory": {
                "type": "static_select",
                "action_id": "model_select",
                # block_id 제거 - accessory 내부에서는 사용 불가
                "placeholder": {
                    "type": "plain_text",
                    "text": "모델을 선택하세요"
                },
                "options": available_models
            }
        },
        {
            "type": "actions",
            "block_id": "model_actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ 적용"
                    },
                    "style": "primary",
                    "action_id": "apply_model_btn",
                    "value": "apply_model"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ 취소"
                    },
                    "action_id": "cancel_model_btn",
                    "value": "cancel_model"
                }
            ]
        }
    ]

    print(f"Slack에 메세지 전송\n")
    client.chat_postMessage(
        channel=slack_user_id,
        blocks=blocks
    )
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "blocks": blocks,
            "text": "AI 모델을 선택하세요",  # text 필드 추가 (경고 해결)
            "response_type": "ephemeral"
        })
    }


def get_selected_model_from_state(payload):
    """
    인터랙션 상태에서 선택된 모델 추출
    """
    try:
        print("get_selected_model_from_state 함수 진입")
        # state.values에서 선택된 값 찾기
        state_values = payload.get('state', {}).get('values', {})
        model_block = state_values.get('model_selection_block', {})
        model_select = model_block.get('model_select', {})
        
        if 'selected_option' in model_select:
            return model_select['selected_option']['value']
            
        # 현재 액션에서도 확인
        for action in payload.get('actions', []):
            if action.get('action_id') == 'model_select':
                return action.get('selected_option', {}).get('value')
                
    except Exception as e:
        print(f"Error extracting selected model: {e}")
    
    return None

def handle_interaction(payload):
    """
    Slack 인터랙션 처리 (드롭다운 선택, 버튼 클릭)
    """
    action_id = payload['actions'][0]['action_id']
    user_id = payload['user']['id']
    print(f"action_id: {action_id}\n")
    print(f"user_id: {user_id}\n")
    
    if action_id == "apply_model_btn":
        selected_model = get_selected_model_from_state(payload)
        print(f"selected_model: {selected_model}\n")
        if selected_model:
            save_user_model_setting(user_id, selected_model)
            model_name = get_model_display_name(selected_model)
            
            print(f"model_name: {model_name}\n")

            print(f"Slack에 메세지 전송\n")
            client.chat_postMessage(
                channel=user_id,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"✅ 모델이 *{model_name}* 로 설정되었습니다!\n"
                                "이제 `/req 질문내용` 으로 사용하세요."
                            )
                        }
                    }
                ]
            )

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "text": f"✅ 모델이 **{model_name}**로 설정되었습니다!\n이제 `/req 질문내용`으로 사용하세요.",
                    "response_type": "ephemeral",
                })
            }
        else:
            print(f"Slack에 메세지 전송\n")
            client.chat_postMessage(
                channel=user_id,
                text="❌ 모델을 먼저 선택해주세요."
            )
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "text": "❌ 모델을 먼저 선택해주세요.",
                    "response_type": "ephemeral"
                })
            }
    
    elif action_id == "cancel_model_btn":
        print(f"Slack에 메세지 전송\n")
        client.chat_postMessage(
            channel=user_id,
            text="모델 선택이 취소되었습니다."
        )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "text": "모델 선택이 취소되었습니다.",
                "response_type": "ephemeral",
                "replace_original": True
            })
        }
    
    elif action_id == "model_select":
        # 드롭다운 선택 시 상태만 업데이트
        return {"statusCode": 200}

def save_user_model_setting(user_id, model_id):
    """
    사용자별 모델 설정을 DynamoDB에 저장
    """
    print(f"save_user_model_setting 함수 진입\n")
    try:
        user_settings_table.put_item(
            Item={
                'user_id': user_id,
                'selected_model': model_id,
                'updated_at': int(time.time())
            }
        )
    except Exception as e:
        print(f"Error saving user setting: {e}")

def get_user_model_setting(user_id):
    """
    사용자의 모델 설정을 DynamoDB에서 조회
    """
    try:
        response = user_settings_table.get_item(
            Key={'user_id': user_id}
        )
        return response.get('Item', {}).get('selected_model', 'claude-3-7-sonnet-20250219')
    except Exception as e:
        print(f"Error getting user setting: {e}")
        return 'claude-3-7-sonnet-20250219'

def get_model_display_name(model_id):
    """
    모델 ID로 display_name 조회
    """
    try:
        print(f"get_model_display_name 함수 진입\n")
        models = get_models_from_api()
        for model in models:
            if model["id"] == model_id:
                return model["display_name"]
    except:
        pass
    return model_id

def filter_analysis_results(history):
    """':brain: 분석 결과:'로 시작하는 메시지만 필터링"""
    filtered_messages = []
    
    for message in history['messages']:
        text = message.get('text', '')
        if text.startswith(':hourglass_flowing_sand:') or text.startswith(':robot_face:') or text.startswith(':x:') or text.startswith(':white_check_mark:') or text.startswith(':closed_lock_with_key:'):
            # 해당 메시지는 유저도 분석결과 아님으로 필터링
            continue
        # 메시지의 role은 'user' 또는 'assistant'로 설정
        elif "error" in text:
            continue
        elif text.startswith(':brain: 분석 결과:'):
            role = 'assistant'
            text = text.split(':brain: 분석 결과:')[1].strip()
            filtered_messages.append({'role': role, 'content': text})
        else:
            role = 'user'
            text = text.strip()
            filtered_messages.append({'role': role, 'content': text})

        print(f"filtered_messages: {filtered_messages}\n")

    return filtered_messages

def handle_req_command(payload):
    """
    /req 명령어 처리 - 저장된 모델로 질문 처리
    """
    print("handle_req_command 함수 실행")
    event = payload.get("event", {})
    
    text = event.get("text", "")
    print(f"text: {text}\n")
    user_id = event.get("user", "")
    print(f"user_id: {user_id}\n")
    channel_id = event.get("channel", "")
    print(f"channel_id: {channel_id}\n")
    if not text or not text.strip():
        return {
            'statusCode': 200,
            'body': json.dumps({
                'text': "❌ 질문을 입력해주세요.\n사용법: `/req 질문내용`\n예시: `/req 안녕하세요?`",
                'response_type': 'ephemeral'
            })
        }
    
    model_id = get_user_model_setting(user_id)
    question = text.strip()
    
    print(f"User: {user_id}, Model: {model_id}, Question: {question}")
    model_name = get_model_display_name(model_id)
    print(f"model_name: {model_name}\n")

    client.chat_postMessage(
        channel=user_id,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"⏳ {model_name}를 사용하여 답변을 생성중입니다....."
                    )
                }
            }
        ]
    )

    print("history 불러오기")
    print(f"slack_channel_id: {channel_id}\n")
    history = client.conversations_history(
        channel=channel_id,
        limit=10
    )

    print(f"history: {history}\n")
    analysis_messages = filter_analysis_results(history)
    print(f"analysis_messages: {analysis_messages}\n")
    print(f"분석 결과 메시지 개수: {len(analysis_messages)}")

    requests.post(
        f"{CONFIG['api']['endpoint']}/llm1",
        json={
            "question": question,
            "modelId": model_id,
            "user_id": user_id,
            "previous_questions": analysis_messages,
        },
    )

    return {
        'statusCode': 200,
    }

def handle_slack_events(event, context):
    event_body = event.get("body") or ""
    headers = event.get('headers', {})
    retry_num = headers.get('X-Slack-Retry-Num')
    retry_reason = headers.get('X-Slack-Retry-Reason')

    # 재시도 요청인 경우 즉시 200 응답
    if retry_num:
        print(f"재시도 요청 감지: {retry_reason} (retry #{retry_num})")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'response_type': 'ephemeral',
                'text': f'Already processing (retry #{retry_num})'
            })
        }
    
    try:
        quick_response = {
            'statusCode': 200,
            'body': json.dumps({
                'response_type': 'ephemeral', 
                'text': 'Processing your request...'
            })
        }

        payload = json.loads(event_body)
        
        # URL 검증
        if payload.get("type") == "url_verification":
            print("URL 검증 진입")
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "text/plain"},
                "body": payload["challenge"]
            }
        
        # 이벤트 콜백 처리
        if payload.get("type") == "event_callback":
            print("이벤트 콜백 진입")
            event_data = payload.get("event", {})
            print(f"event_data: {event_data}\n")

            # 봇 메시지 필터링 (중요!)
            if event_data.get("bot_id"):
                print(f"봇 메시지 감지: {event_data.get('bot_id')}")
                print("봇 메시지이므로 무시")
                return {"statusCode": 200}
            
            # 사용자 메시지만 처리
            if event_data.get("type") == "message" and "user" in event_data:
                return handle_req_command(payload)
        
        return quick_response
        
    except Exception as e:
        print(f"이벤트 처리 오류: {e}")
        return {
            'statusCode': 200,  # 에러여도 200 반환
            'body': json.dumps({
                'response_type': 'ephemeral',
                'text': 'Error occurred, please try again'
            })
        }
