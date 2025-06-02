# llm/lambda_function.py
import requests
from llm_service import parse_body, handle_llm1_request, handle_llm2_request, handle_llm1_with_mcp, get_anthropic_models
from common.config import get_config
from common.utils import cors_response


def lambda_handler(event, context):
    CONFIG = get_config()
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")
    origin = event.get("headers", {}).get("origin", f"https://{CONFIG['amplify']['default_domain_with_env']}")

    if http_method == "OPTIONS":
        response = cors_response(200, "", origin)
        return response

    try:
        body = parse_body(event) or {}
        if path == "/health" and http_method == "GET":
            # Anthropic 모델 목록 조회
            models = get_anthropic_models()

            response_data = {
                "status": "ok",
                "models": models
            }

            return cors_response(200, response_data, origin)

        elif path == "/llm1" and http_method == "POST":
            return handle_llm1_with_mcp(body, origin)

        else:
            return cors_response(404, {"error": f"Route {http_method} {path} not found."}, origin)

    except Exception as e:
        return cors_response(500, {"error": "Internal server error", "detail": str(e)}, origin)