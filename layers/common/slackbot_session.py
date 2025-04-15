# common/slackbot_session.py
import boto3

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
