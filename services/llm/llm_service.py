import json
import urllib.parse
import requests
import boto3
import os
import time
from common.config import get_config
from common.utils import invoke_bedrock_nova, cors_headers, cors_response
from slack_sdk import WebClient

# CloudWatch Logs client
def get_logs_client():
    return boto3.client('logs', region_name=os.environ.get('AWS_REGION'))

# 1) Log Group 목록 조회 기능
def list_log_groups(prefix=None, limit=50):
    """
    현재 계정의 CloudWatch Log Groups 목록을 반환
      - prefix: 이름 접두어로 필터링 (없으면 전체)
      - limit: 페이지당 조회 개수
    """
    logs = get_logs_client()
    paginator = logs.get_paginator('describe_log_groups')
    params = {'limit': limit}
    if prefix:
        params['logGroupNamePrefix'] = prefix

    groups = []
    for page in paginator.paginate(**params):
        for g in page.get('logGroups', []):
            groups.append({
                'logGroupName': g['logGroupName'],
                'creationTime': g['creationTime'],
                'retentionInDays': g.get('retentionInDays')
            })
    print(f"Log groups: {groups}")
    return groups

# 2) CloudWatch Logs Insights 쿼리 기능
def call_insights_query(log_group, query_string, start_time, end_time, limit=100):
    """
    CloudWatch Logs Insights 쿼리 실행 후 결과 반환
    """
    logs = get_logs_client()
    resp = logs.start_query(
        logGroupNames=[log_group],
        startTime=start_time,
        endTime=end_time,
        queryString=query_string,
        limit=limit
    )
    query_id = resp['queryId']

    # 완료 대기
    while True:
        status_resp = logs.get_query_results(queryId=query_id)
        status = status_resp['status']
        if status in ('Complete', 'Failed', 'Cancelled'):
            print(f">>> 쿼리 상태: {status}")
            break
        time.sleep(1)

    results = status_resp.get('results', [])
    # Debug: raw 결과 출력
    print(">>> call_insights_query 원본 결과:")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    # 빈 리스트 대체 로직
    if not results:
        print(f">>> 빈 결과 ")

    return results

def get_table_registry():
    dynamodb = boto3.resource("dynamodb")
    table_name = os.environ.get("ATHENA_TABLE_REGISTRY_TABLE")
    table = dynamodb.Table(table_name)
    response = table.scan()
    return {item["log_type"]: item for item in response.get("Items", [])}

def call_mcp_service(user_question):
    CONFIG = get_config()
    payload = {
        "input": {
            "text": user_question
        }
    }
    response = requests.post(CONFIG['mcp']['function_url'], json=payload)
    return response.json()

def build_llm1_prompt(user_input):
    registry = get_table_registry()
    if "cloudtrail" in registry and "guardduty" in registry:
        ct_table = registry["cloudtrail"]["table_name"]
        ct_location = registry["cloudtrail"]["s3_path"]
        gd_table = registry["guardduty"]["table_name"]
        gd_location = registry["guardduty"]["s3_path"]
        tables_info = f"""
Available tables:
1. {ct_table} - CloudTrail logs at {ct_location}
2. {gd_table} - GuardDuty logs at {gd_location}
        """
    else:
        print("WARNING: Table registry information missing")
        tables_info = """
Available tables:
1. cloudtrail_logs - CloudTrail logs 
2. guardduty_logs - GuardDuty logs
        """

    return f'''
You are a SQL generation expert for AWS Athena (Presto SQL).
Generate ONLY SQL code that is valid in Athena with no explanation.

{tables_info}

Task:
Convert the following natural language question into an SQL query using the available tables.

Decision step (MUST):
- If the request is about CloudTrail / GuardDuty / AWS 보안 로그 분석, output ONLY valid Athena SQL.
- Otherwise (greetings, DevOps 개념 설명, 날씨 등) output EXACTLY: ###IGNORED###

Model Instructions:
    # Output Requirements:
        - Return only the SQL code, no explanations.
        - If filtering by date, use the `"partition_date"` field only.
        - If counting unique users, use `COUNT(DISTINCT userIdentity.userName)`.
        - If you use a field that is not aggregated (like username), you must include it in the GROUP BY clause.
        - Avoid using non-aggregated expressions in SELECT unless they are grouped.
        - If filtering by user name, exclude records where useridentity.username is null or empty string.
        - Use IS NOT NULL AND useridentity.username != '' to ensure only valid user names are considered.
        - If partition_date is a string like yyyy/MM/dd, use date_parse(partition_date, '%Y/%m/%d') to convert it before filtering by date.

User Question:
{user_input}
'''

def build_llm2_prompt(user_input, query_result):
    return f'''
You are an assistant that provides clear and accurate natural language explanations based on database query results.

Task:
Generate a human-readable answer based on the original user question and the SQL query result.

# Expections(MUST):
- If the SQL query result is empty or ###IGNORED###, respond directly : "죄송합니다. 이 시스템은 AWS 보안 로그 관련 질문에만 답변합니다."

Original User Question:
{user_input}

SQL Query Result (as JSON):
{json.dumps(query_result, indent=2)}

Instructions:
- Be specific using the data.
- Use concise, professional language.
- Answer in Korean
- Do not ask user for clarification.
- If the original query includes grouping or aggregation, make sure to reflect the logic accurately.
- Highlight any anomalies or low counts if the data is sparse.
'''

def parse_body(event):
    content_type = event.get("headers", {}).get("Content-Type", "") or \
                   event.get("headers", {}).get("content-type", "")
    
    raw_body = event.get("body") or ""

    if "application/json" in content_type:
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            print("❗ 잘못된 JSON body:", raw_body)
            return {}
    
    elif "application/x-www-form-urlencoded" in content_type:
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw_body).items()}
    
    return {}

def call_create_table_cloudtrail():
    CONFIG = get_config()
    payload = {
        "log_type": "cloudtrail",
        "s3_path": "s3://wga-cloudtrail-2/AWSLogs/339712974607/CloudTrail/us-east-1/",
        "table_name": "cloudtrail_logs"
    }
    return requests.post(f'{CONFIG['api']['endpoint']}/create-table', json=payload) 

def call_create_table_guardduty():
    CONFIG = get_config()
    payload = {
        "log_type": "guardduty",
        "s3_path": "s3://wga-guardduty-logs/guardduty-logs/",
        "table_name": "guardduty_logs"
    }
    return requests.post(f'{CONFIG['api']['endpoint']}/create-table', json=payload) 

def call_execute_query(sql_query):
    CONFIG = get_config()
    wrapper_payload = {
        "query": sql_query
    }
    res = requests.post(f'{CONFIG['api']['endpoint']}/execute-query', json=wrapper_payload)
    return res.json()

def send_slack_dm(user_id, message):
    CONFIG = get_config()
    client = WebClient(token=CONFIG['slackbot']['token'])
    response = client.chat_postMessage(
        channel=user_id,
        text=message
    )
    if not response["ok"]:
        print("❌ Slack 메시지 실패 사유:", response["error"])
    return response

def is_ignored(text: str) -> bool:
    """LLM-1 결과가 ###IGNORED### 인지 판정"""
    return text.strip() == "###IGNORED###"

# 3) Insights 쿼리 생성 함수 (Log Group 동적 선택 포함)
def generate_insights_query(user_question):
    # 사용 가능한 log group 목록 가져오기

    try:
        log_groups = list_log_groups()
        log_group_names = [g['logGroupName'] for g in log_groups]
    except Exception as e:
        print(f"Log groups 조회 실패: {e}")
        return {"log_group": None, "query": " "}

    print(">>> 일단 로그그룹은 통과")

 
    # 3) prompt 생성
    prompt = f'''
You are an expert in generating CloudWatch Logs Insights queries.
Do NOT include any time clauses like "from…ago" in the query itself.
Instead, decide the appropriate time window based on the user's question,
and return that as epoch milliseconds in start_time and end_time.

Available Log Groups:
{ "\n".join(log_group_names) }

User Question:
{user_question}

Return FORMAT (JSON):
{{
  "log_group": string,      # 선택된 Log Group 이름
  "query": string,          # 유효한 Insights 쿼리 (시간 필터 없이)
  "start_time": number,     # 시작 시각 (epoch 초 단위)
  "end_time": number        # 종료 시각 (epoch 초 단위)
}}

EXAMPLE:
{{
  "log_group": "/aws/lambda/wga-llm-test",
  "query": "fields @timestamp | filter detail.type = \\"Recon:EC2\\" | stats count() as threat_count by bin(1h)",
  "start_time": 시작시각,
  "end_time": 종료시각
}}

Only output the JSON—no explanations.
'''
    print(">>> prompt 길이:", len(prompt))

    try:
        response = invoke_bedrock_nova(prompt)
        raw = response["output"]["message"]["content"][0]["text"]
        result = json.loads(raw)
        print(">>> generate_insights_query end:", result)
        return result
    except Exception as e:
        print("❌ generate_insights_query error:", e)
        # fallback: 기존 하드코딩 (지난 7일)
        now = int(time.time() * 1000)
        week_ago = now - 7 * 24 * 3600 * 1000
        return {
            "log_group": next((g for g in log_group_names if "guardduty" in g.lower()), log_group_names[0]),
            "query": 'fields @timestamp | stats count() as threat_count',
            "start_time": week_ago,
            "end_time": now
        }

def handle_llm1_request(body, CONFIG, origin):
    user_question = body.get("text")
    slack_user_id = body.get("user_id")

    if not user_question:
        return cors_response(400, {"error": "request body에 'text'가 없음."}, origin)

    print(f"처리 중인 질문: {user_question}")
    
    # 테이블 레지스트리 정보 확인
    registry = get_table_registry()
    print(f"테이블 레지스트리: {registry}")
    
    # 분류 프롬프트
    classification_prompt = f"""
다음 질문이 AWS CloudTrail 로그나 GuardDuty 로그에서 데이터를 쿼리해야 하는 질문인지,
AWS 공식 문서나 정보를 찾아봐야 하는 질문인지, 아니면 앞에서 설명한 내용과 무관한 질문인지 판단하시오.

가능한 응답:
- "QUERY": CloudTrail이나 GuardDuty 로그 데이터를 분석해야 하는 질문
- "DOCUMENT": AWS 서비스, 개념, 기능 등에 대한 설명이나 정보가 필요한 질문
- "CLOUDWATCH": CloudWatch Logs Insights 쿼리를 직접 실행해야 하는 질문
- "USELESS": QUERY, DOCUMENT, CLOUDWATCH에 해당하지 않는, 무관한 질문

질문: {user_question}

응답 (QUERY, DOCUMENT, CLOUDWATCH, USELESS만 작성):
"""
    
    classification_result = invoke_bedrock_nova(classification_prompt)
    decision = classification_result["output"]["message"]["content"][0]["text"].strip()
    print(f"분류 결과: {decision}")
    
    # 2단계: 분류 결과에 따라 적절한 서비스로 라우팅
    if "QUERY" in decision:
        # 기존 로직: SQL 쿼리 생성 및 실행
        prompt = build_llm1_prompt(user_question)
        sql_query = invoke_bedrock_nova(prompt)
        raw_text = sql_query["output"]["message"]["content"][0]["text"]

        if is_ignored(raw_text):
            cleaned_query_result = "###IGNORED###"
        else:
            cleaned = raw_text.strip().removeprefix("```sql").removesuffix("```").strip()
            call_create_table_cloudtrail()
            call_create_table_guardduty()
            cleaned_query_result = call_execute_query(cleaned)

        llm2_response = requests.post(
            f"{CONFIG['api']['endpoint']}/llm2",
            json={
                "question": user_question,
                "result": cleaned_query_result
            }
        )

        try:
            llm2_answer = llm2_response.json().get("answer", "[답변 생성 실패]")
            if isinstance(llm2_answer, str):
                text_answer = llm2_answer
            else:
                text_answer = llm2_answer.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "[답변 없음]")
        except Exception as parse_error:
            print("응답 파싱 실패:", str(parse_error))
            text_answer = "[답변 파싱 실패]"

    elif "DOCUMENT" in decision:
        mcp_response = call_mcp_service(user_question)
        text_answer = mcp_response.get("result", "[MCP 응답 없음]")
    elif "CLOUDWATCH" in decision:
        # CloudWatch Logs Insights 쿼리 생성
        
        insights_result = generate_insights_query(user_question)
        
        if insights_result["query"] == "###IGNORED###" or not insights_result["log_group"]:
            text_answer = "죄송합니다. 이 시스템은 AWS 보안 로그 관련 질문에만 답변합니다."
        else:
            try:
                # 쿼리 실행 (동적 log group 사용)
                query_result = call_insights_query(
                    log_group=insights_result["log_group"],
                    query_string=insights_result["query"],
                    start_time=int((time.time() - 7 * 24 * 3600) * 1000),  # 지난 7일
                    end_time=int(time.time() * 1000)
                )
                # llm2 엔드포인트로 결과 전송 (QUERY와 동일한 방식)
                llm2_response = requests.post(
                    f"{CONFIG['api']['endpoint']}/llm2",
                    json={
                        "question": user_question,
                        "result": query_result
                    }
                )
                print(">>> llm2 status:", llm2_response.status_code)
                print(">>> llm2 body:", llm2_response.text)
                try:
                    llm2_answer = llm2_response.json().get("answer", "[답변 생성 실패]")
                    if isinstance(llm2_answer, str):
                        text_answer = llm2_answer
                    else:
                        text_answer = llm2_answer.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "[답변 없음]")
                except Exception as parse_error:
                    print("응답 파싱 실패:", str(parse_error))
                    text_answer = "[답변 파싱 실패]"
            except Exception as e:
                print(f"CloudWatch 쿼리 실행 실패: {str(e)}")
                text_answer = "CloudWatch 쿼리 실행 중 오류가 발생했습니다."
    else:
        text_answer = "죄송합니다. 이 시스템은 AWS 운영정보 혹은 메뉴얼 관련 질문에만 답변합니다."

    # 최종 결과를 Slack으로 전송
    try:
        #send_slack_dm(slack_user_id, f"🧠 분석 결과:\n{text_answer}")
        print(1)
    except Exception as e:
        print(f"Slack 전송 실패: {str(e)}")
        text_answer += "\n(Slack 전송 실패)"

    return cors_response(200, {
        "status": "질문 처리 완료",
        "answer": text_answer
    }, origin)

def handle_llm2_request(body, CONFIG, origin):
    user_question = body.get("question")
    query_result = body.get("result")

    if not user_question or not query_result:
        return cors_response(400, {"error": "request body에 'question' 이나 'result'가 없음."}, origin)

    prompt = build_llm2_prompt(user_question, query_result)
    answer = invoke_bedrock_nova(prompt)
    return cors_response(200, {"answer": answer}, origin)
