# lambda_function.py
from common.utils import invoke_bedrock_nova
from llm_service import build_llm1_prompt, build_llm2_prompt
import json

def lambda_handler(event, context):
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")
    body = json.loads(event.get("body", "{}"))

    if path == "/health" and http_method == "GET":
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "ok"})
        }

    elif path == "/llm1" and http_method == "POST":
        user_question = body.get("question")
        if not user_question:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "request body에 'question'이 없음."})
            }

        prompt = build_llm1_prompt(user_question)
        sql_query = call_nova(prompt)

        return {
            "statusCode": 200,
            "body": json.dumps({"sql": sql_query})
        }

    elif path == "/llm2" and http_method == "POST":
        user_question = body.get("question")
        query_result = body.get("result")

        if not user_question or not query_result:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "request body에 'question' 이나 'result'가 없음."})
            }

        prompt = build_llm2_prompt(user_question, query_result)
        answer = invoke_bedrock_nova(prompt)

        return {
            "statusCode": 200,
            "body": json.dumps({"answer": answer})
        }

    else:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": f"Route {http_method} {path} not found."})
        }
