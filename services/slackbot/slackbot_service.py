from common.slackbot_session import get_session
from slack_sdk import WebClient
from common.config import CONFIG
import threading
import boto3
import os

print("==== Lambda 호출됨 ====")
ssm = boto3.client("ssm")
path = os.environ.get("SLACK_BOT_TOKEN_PATH")
domain = os.environ.get("COGNITO_DOMAIN_PATH")
client_id = os.environ.get("COGNITO_CLIENT_ID_PATH")
endpoint = os.environ.get("API_ENDPOINT")

client = WebClient(token=path)

def handle_login_command(slack_user_id: str, channel_id: str):
    # 응답을 지연시키지 않기 위해 백그라운드로 실행
    threading.Thread(target=send_login_button, args=(slack_user_id,)).start()
    
    # 슬랙 slash command 요청에 즉시 응답 (Slack이 요구하는 3초 제한 대응)
    return {
        "statusCode": 200,
        "body": "🔐 로그인 링크를 전송 중입니다..."
    }

def send_login_button(slack_user_id):
    login_url = (
        f"{domain}/oauth2/authorize"
        "?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri=https://2nkfifjwil.execute-api.us-east-1.amazonaws.com/dev/callback"
        f"&scope=openid+email+profile&state={slack_user_id}"
    )

    print(login_url)

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

def handle_protected_command(slack_user_id: str):
    session = get_session(slack_user_id)

    if not session:
        client.chat_postMessage(
            channel=slack_user_id,
            text="❗ 로그인이 필요합니다. `/login`을 입력해주세요."
        )
        return

    access_token = session["access_token"]
    client.chat_postMessage(
        channel=slack_user_id,
        text=f"✅ 로그인 상태입니다. 토큰 일부: `{access_token[:10]}...`"
    )