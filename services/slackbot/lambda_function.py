import requests
import urllib.parse
import json
from common.config import get_config
from common.slackbot_session import get_session, save_session, send_slack_dm, send_slack_channel_message
from slackbot_service import send_login_button, handle_models_command, handle_interaction, handle_req_command
from jose import jwt

def lambda_handler(event, context):
    body = event.get("body") or ""
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")
    CONFIG = get_config()

    if path == "/login" and http_method == "POST":
        body = urllib.parse.parse_qs(event["body"])
        slack_user_id = body.get("user_id", [""])[0]
        send_login_button(slack_user_id)
        return {
            "statusCode": 200,
            "body": "🔐 로그인 링크를 Slack DM으로 전송했습니다!"
        }
    
    elif path == "/callback" and http_method == "GET":
        params = event.get("queryStringParameters") or {}
        code = params.get("code")
        slack_user_id = params.get("state")

        if not code or not slack_user_id:
            return {
                "statusCode": 200,
                "body": "<h3>❗ Access Deined. Please login in slack first.</h3>",
                "headers": {"Content-Type": "text/html"}
            }

        # Cognito 토큰 교환
        res = requests.post(
            f"{CONFIG['cognito']['domain']}/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CONFIG['cognito']['client_id'],
                "code": code,
                "redirect_uri": f"{CONFIG['api']['endpoint']}/callback" # Api ENDPOINT/callback URL 입력
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if res.status_code != 200:
            return {
                "statusCode": 500,
                "body": "Token Exchange Failed",
                "headers": {"Content-Type": "text/html"}
            }

        tokens = res.json()
        # 여기에 access_token, id_token 저장 or 검증

        user_info = jwt.decode(tokens["id_token"], key="", access_token=tokens["access_token"], options={"verify_signature": False, "verify_aud": False})
        email = user_info.get("email")

        save_session(
            slack_user_id=slack_user_id,
            access_token=tokens["access_token"],
            id_token=tokens["id_token"],
            email=email
        )

        return {
            "statusCode": 200,
            "body": "<h3>Login Complete!!.</h3>",
            "headers": {"Content-Type": "text/html"}
        }
    # Slack Slash Command 처리
    elif path == "/models" and http_method == "POST":
        body = urllib.parse.parse_qs(event["body"])
        slack_user_id = body.get("user_id", [""])[0]

        try:
            print("/models 진입\n")
            handle_models_command(slack_user_id)
            return {
            "statusCode": 200,
            }
            
        except Exception as e:
            print(f"Error processing slash command: {e}")

    elif path == "/req" and http_method == "POST":
        body = urllib.parse.parse_qs(event["body"])
        slack_user_id = body.get("user_id", [""])[0]
        try:
            print("/req 진입\n")
            command = body.get('command', [''])[0]
            text = body.get('text', [''])[0]

            return handle_req_command(text, slack_user_id)

        except Exception as e:
            print(f"Error processing slash command: {e}")

    elif path == "/slack-interactions" and http_method == "POST":
        parsed_data = urllib.parse.parse_qs(body)
        payload_str = parsed_data.get('payload', [''])[0]
        payload = json.loads(payload_str)

        print(f"Interaction payload: {payload}")
        
        if payload.get('type') == 'block_actions':
            handle_interaction(payload)
            return handle_interaction(payload)

    else:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": f"Route {http_method} {path} not found."})
        }