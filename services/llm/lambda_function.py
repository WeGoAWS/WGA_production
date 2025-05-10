# llm/lambda_function.py
import requests
from llm_service import parse_body, handle_llm1_request, handle_llm2_request
from common.config import get_config
from common.utils import cors_response


def lambda_handler(event, context):
    CONFIG = get_config()
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")

    # 이 부분에서 origin을 더 유연하게 처리하도록 수정
    origin = event.get("headers", {}).get("origin", "")

    # origin이 없거나 빈 문자열인 경우 기본값 설정
    if not origin:
        origin = f"https://{CONFIG['amplify']['default_domain_with_env']}"

    # origin을 허용된 목록과 비교하여 유효성 검사 (선택 사항)
    allowed_origins = [
        f"https://{CONFIG['amplify']['default_domain_with_env']}",
        f"https://{Environment}.{CONFIG['frontend']['redirect_domain']}",  # CloudFormation에서 가져온 값
        "http://localhost:5173"  # 로컬 개발 환경
    ]

    # 요청의 origin이 허용 목록에 없는 경우 기본값 사용
    if origin not in allowed_origins:
        # 허용된 목록에 없는 도메인의 경우 기본값을 사용하거나,
        # 모든 도메인을 허용하려면 아래 주석을 해제하세요
        # origin = "*"  # 모든 도메인 허용 (보안에 주의)
        origin = f"https://{CONFIG['amplify']['default_domain_with_env']}"  # 기본값 사용

    if http_method == "OPTIONS":
        response = cors_response(200, "", origin)
        return response

    try:
        body = parse_body(event) or {}
        if path == "/health" and http_method == "GET":
            return cors_response(200, {"status": "ok"}, origin)

        elif path == "/llm1" and http_method == "POST":
            return handle_llm1_request(body, CONFIG, origin)

        elif path == "/llm2" and http_method == "POST":
            return handle_llm2_request(body, CONFIG, origin)

        else:
            return cors_response(404, {"error": f"Route {http_method} {path} not found."}, origin)

    except Exception as e:
        return cors_response(500, {"error": "Internal server error", "detail": str(e)}, origin)