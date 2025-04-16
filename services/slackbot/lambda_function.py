import requests
import urllib.parse
import json
from common.config import get_config
from common.slackbot_session import save_session
from jose import jwt
from slackbot_service import send_login_button

def lambda_handler(event, context):
    body = event.get("body") or ""
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")
    CONFIG = get_config()
    print("path:", path)
    if path == "/slackbot" and http_method == "POST":
        body = urllib.parse.parse_qs(event["body"])
        slack_user_id = body.get("user_id", [""])[0]
        send_login_button(slack_user_id)
        return {
            "statusCode": 200,
            "body": "🔐 로그인 링크를 Slack DM으로 전송했습니다!"
        }

    elif path =="/callback" and http_method == "GET":
        params = event.get("queryStringParameters") or {}
        code = params.get("code")
        slack_user_id = params.get("state")

        if not code or not slack_user_id:
            return {
                "statusCode": 200,
                "body": "<h3>❗ 유효하지 않은 접근입니다. 슬랙에서 로그인 버튼을 먼저 눌러주세요.</h3>",
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
        print("슬랙 사용자:", slack_user_id)
        print("토큰:", tokens)

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
            "body": "<h3>✅ 로그인이 완료되었습니다.</h3>",
            "headers": {"Content-Type": "text/html"}
        }

    else:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": f"Route {http_method} {path} not found."})
        }