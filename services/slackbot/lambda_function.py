import requests
import urllib.parse
import json
from common.config import get_config
from common.slackbot_session import get_session, save_session, send_slack_dm, send_slack_channel_message
from slackbot_service import send_login_button
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
    elif path == "/events" and http_method == "POST":
        slack_event = json.loads(body)

        # URL 검증을 위한 challenge 응답
        if slack_event.get("type") == "url_verification":
            return {
                "statusCode": 200,
                "body": slack_event.get("challenge")
            }

        # 이벤트 콜백 처리
        if slack_event.get("type") == "event_callback":
            event_data = slack_event.get("event", {})
            user_id = event_data.get("user")
            text = event_data.get("text", "")
            channel = event_data.get("channel")

            # 봇 자신의 메시지는 무시
            if "bot_id" in event_data:
                return {"statusCode": 200}

            # 봇 멘션 부분 제거
            bot_user_id = CONFIG["bot_user_id"]
            question = text.replace(f"<@{bot_user_id}>", "").strip()

            # 세션 확인
            session = get_session(user_id)
            if not session:
                send_login_button(user_id)
                send_slack_channel_message(channel, f"<@{user_id}>님, 먼저 로그인이 필요합니다. Slack DM에서 로그인 버튼을 확인해주세요.")
                return {"statusCode": 200}

            # /llm1 Lambda 호출
            try:
                response = requests.post(
                    f"{CONFIG['api']['endpoint']}/llm1",
                    json={"text": question, "user_id": user_id},
                    headers={"Origin": CONFIG["frontend"]["redirect_domain"]}
                )
                result = response.json()
                answer = result.get("answer", "❗ 답변을 가져오지 못했습니다.")
            except Exception as e:
                print("LLM1 호출 실패:", e)
                answer = "❗ 처리 중 오류가 발생했습니다."

            send_slack_channel_message(channel, answer)

            return {"statusCode": 200}

        return {"statusCode": 400, "body": "Unsupported event"}

    elif path == "/callback" and http_method == "GET":
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