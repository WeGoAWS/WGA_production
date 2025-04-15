# lambda_function.py
from common.utils import invoke_bedrock_nova
from llm_service import build_llm1_prompt, build_llm2_prompt, parse_body, call_create_table_guardduty, call_create_table_cloudtrail, call_execute_query, send_slack_dm
from common.config import CONFIG
import json
import requests

def lambda_handler(event, context):
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")
    body = parse_body(event)

    user_question = body.get("text")
    slack_user_id = body.get("user_id")

    print(f"Path: {path}, Method: {http_method}, Body: {body}")

    if path == "/health" and http_method == "GET":
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "ok"})
        }

    elif path == "/llm1" and http_method == "POST":
        user_question = body.get("text")
        if not user_question:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "request body에 'text'가 없음."})
            }

        prompt = build_llm1_prompt(user_question)
        sql_query = invoke_bedrock_nova(prompt)
        raw_text = sql_query["output"]["message"]["content"][0]["text"]
        cleaned = raw_text.strip().removeprefix("```sql").removesuffix("```").strip()

        call_create_table_cloudtrail()
        call_create_table_guardduty()
        print("전달할 쿼리: ", cleaned)
        cleaned_query_result = call_execute_query(cleaned)
        print("쿼리 결과: ", cleaned_query_result)
        llm2_response = requests.post(
            f'{CONFIG['api']['endpoint']}/llm2', # 여기에 LLM2 API URL을 입력하세요
            json={
                "question": user_question,
                "result": cleaned_query_result
            }
        )
        llm2_answer = llm2_response.json().get("answer", "[답변 생성 실패]")
        send_slack_dm(slack_user_id, f"🧠 분석 결과:\n{llm2_answer["output"]["message"]["content"][0]["text"]}")
        
        return {"statusCode": 200, "body": json.dumps({"status": "쿼리 생성 및 DM 전송 완료"})}


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
