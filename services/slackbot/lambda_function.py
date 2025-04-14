import requests
import os
from common.config import CONFIG
from common.slackbot_session import save_session
import jwt

def lambda_handler(event, context):
    params = event["queryStringParameters"]
    code = params["code"]
    slack_user_id = params["state"]

    # Cognito 토큰 교환
    res = requests.post(
        f"https://{CONFIG['cognito']['domain']}.auth.us-east-1.amazoncognito.com/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": CONFIG['cognito']['client_id'],
            "code": code,
            "redirect_uri": f"{CONFIG['api']['endpoint']}/callback"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    tokens = res.json()
    # 여기에 access_token, id_token 저장 or 검증
    print("슬랙 사용자:", slack_user_id)
    print("토큰:", tokens)

    user_info = jwt.decode(tokens["id_token"], options={"verify_signature": False})
    email = user_info.get("email")

    save_session(
        slack_user_id=slack_user_id,
        access_token=tokens["access_token"],
        id_token=tokens["id_token"],
        email=email
    )
    
    return {
        "statusCode": 200,
        "body": "<h2>로그인 성공 🎉</h2> 이제 슬랙에서 질문하세요.",
        "headers": {"Content-Type": "text/html"}
    }