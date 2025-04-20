# llm/lambda_function.py
from common.utils import invoke_bedrock_nova
from llm_service import (
    build_llm1_prompt,
    build_llm2_prompt,
    parse_body,
    call_create_table_guardduty,
    call_create_table_cloudtrail,
    call_execute_query,
    send_slack_dm
)
from common.config import get_config
import json
import requests

def cors_headers(origin):
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
        "Access-Control-Allow-Headers": "Authorization,Content-Type",
        "Access-Control-Allow-Credentials": "true"
    }

def cors_response(status_code, body, origin):
    return {
        "statusCode": status_code,
        "headers": cors_headers(origin),
        "body": json.dumps(body) if isinstance(body, dict) else body
    }

def lambda_handler(event, context):
    CONFIG = get_config()
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")
    origin = event.get("headers", {}).get("origin", f"https://{CONFIG['amplify']['default_domain_with_env']}")

    # OPTIONS 요청 먼저 처리
    if http_method == "OPTIONS":
        response = cors_response(200, "", origin)
        print("OPTIONS response:", response)
        return response

    try:
        body = parse_body(event) or {}
        print(f"Path: {path}, Method: {http_method}, Body: {body}")

        if path == "/health" and http_method == "GET":
            return cors_response(200, {"status": "ok"}, origin)

        elif path == "/llm1" and http_method == "POST":
            user_question = body.get("text")
            slack_user_id = body.get("user_id")

            if not user_question:
                return cors_response(400, {"error": "request body에 'text'가 없음."}, origin)

            prompt = build_llm1_prompt(user_question)
            sql_query = invoke_bedrock_nova(prompt)
            raw_text = sql_query["output"]["message"]["content"][0]["text"]
            cleaned = raw_text.strip().removeprefix("```sql").removesuffix("```").strip()

            call_create_table_cloudtrail()
            call_create_table_guardduty()
            print("전달할 쿼리:", cleaned)
            cleaned_query_result = call_execute_query(cleaned)
            print("쿼리 결과:", cleaned_query_result)

            llm2_response = requests.post(
                f"{CONFIG['api']['endpoint']}/llm2",
                json={
                    "question": user_question,
                    "result": cleaned_query_result
                }
            )
            llm2_answer = llm2_response.json().get("answer", "[답변 생성 실패]")
            text_answer = llm2_answer.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "[답변 없음]")

            send_slack_dm(slack_user_id, f"🧠 분석 결과:\n{text_answer}")

            return cors_response(200, {
                "status": "쿼리 생성 완료",
                "answer": text_answer
            }, origin)

        elif path == "/llm2" and http_method == "POST":
            user_question = body.get("question")
            query_result = body.get("result")

            if not user_question or not query_result:
                return cors_response(400, {"error": "request body에 'question' 이나 'result'가 없음."}, origin)

            prompt = build_llm2_prompt(user_question, query_result)
            answer = invoke_bedrock_nova(prompt)

            return cors_response(200, {"answer": answer}, origin)

        else:
            return cors_response(404, {"error": f"Route {http_method} {path} not found."}, origin)

    except Exception as e:
        print("Unhandled exception:", str(e))
        return cors_response(500, {"error": "Internal server error", "detail": str(e)}, origin)
