from common.slackbot_session import get_session
from slack_sdk import WebClient
from common.config import get_config

print("==== Lambda 호출됨 ====")
CONFIG = get_config()
client = WebClient(token=CONFIG["slackbot"]["token"])

def send_login_button(slack_user_id):
    login_url = (
        f"{CONFIG['cognito']['domain']}/oauth2/authorize"
        "?response_type=code"
        f"&client_id={CONFIG['cognito']['client_id']}"
        f"&redirect_uri={CONFIG['api']['endpoint']}/callback" # Api ENDPOINT/callback URL 입력
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