# common/slackbot_session.py
import boto3
from common.config import get_config
from slack_sdk import WebClient

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("SlackbotSessions")

def save_session(slack_user_id: str, access_token: str, id_token: str, email: str) -> None:
    table.put_item(Item={
        "slack_user_id": slack_user_id,
        "access_token": access_token,
        "id_token": id_token,
        "email": email
    })

def get_session(slack_user_id: str) -> dict | None:
    response = table.get_item(Key={"slack_user_id": slack_user_id})
    return response.get("Item")

def delete_session(slack_user_id: str) -> None:
    table.delete_item(Key={"slack_user_id": slack_user_id})

def send_slack_dm(user_id, message):
    try:
        CONFIG = get_config()
        client = WebClient(token=CONFIG['slackbot']['token'])

        if not user_id:
            print("⚠️ user_id 없음. Slack 전송 생략.")
            return

        response = client.chat_postMessage(
            channel=user_id,
            text=message
        )

        if not response["ok"]:
            print("❌ Slack 메시지 실패:", response["error"])

    except Exception as e:
        print("Slack API 예외 발생:", str(e))
