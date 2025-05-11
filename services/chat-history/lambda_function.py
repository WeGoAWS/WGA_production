import json
from urllib.parse import parse_qs
from common.utils import cors_response
from common.config import get_config
from chat_history_service import handle_chat_history_request

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
            return cors_response(200, {"status": "ok"}, origin)

        elif path.startswith("/sessions"):
            return handle_chat_history_request(path, http_method, body, event, origin)

        else:
            return cors_response(404, {"error": f"Route {http_method} {path} not found."}, origin)

    except Exception as e:
        return cors_response(500, {"error": "Internal server error", "detail": str(e)}, origin)

def parse_body(event):
    """이벤트에서 본문 파싱"""
    body = event.get('body', '{}')

    content_type = event.get('headers', {}).get('content-type', '')
    if 'application/json' in content_type:
        return json.loads(body)
    elif 'application/x-www-form-urlencoded' in content_type:
        return {k: v[0] for k, v in parse_qs(body).items()}
    else:
        try:
            return json.loads(body)
        except:
            return {}