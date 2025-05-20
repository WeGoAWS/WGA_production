import json
import urllib.parse
import requests
import boto3
import os
import time
import datetime
from datetime import datetime, timezone
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

def trans_eng_to_kor(text):
    prompt = f"""
You are a professional translator.
The following text may include a list of citations in dictionary-like format.
Translate only the explanation sentences into Korean.

- Remove any technical field names like 'rank_order', 'context', 'title', 'url'.
- Preserve any URLs and titles.
- Do NOT translate URLs or titles.
- Format the result cleanly so that each citation appears as:

한국어 번역된 설명
원래 제목
원래 URL

Translate the text below accordingly.
Only Generate Translate.

Text to translate:
{text}
"""
    response = invoke_bedrock_nova(prompt)
    trans_response = response["output"]["message"]["content"][0]["text"]
    return trans_response


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
def is_ignored(raw_text_sql):
    # "###IGNORED###" 또는 "N/A"가 포함된 경우 True 반환
    if raw_text_sql.startswith("###IGNORED###") or raw_text_sql == "N/A":
        return True
    # 그 외의 경우 False 반환
    return False
def handle_llm1_request(body, CONFIG, origin):
    question_time = datetime.now(timezone.utc) # 질문 시작 시간 기록
    user_question = body.get("text")
    slack_user_id = body.get("user_id")

    if not user_question:
        return cors_response(400, {"error": "request body에 'text'가 없음."}, origin)

    print(f"처리 중인 질문: {user_question}")

    # 테이블 레지스트리 정보 확인
    registry = get_table_registry() # 이 함수는 common.utils 또는 llm_service 내에 정의되어 있어야 합니다.
    print(f"테이블 레지스트리: {registry}")

    # 분류 프롬프트
    classification_prompt = f"""
Determine whether the following questions should be queried data from the AWS CloudTrail or GuardDuty logs, 
look up AWS official documents or information, or are irrelevant to what was previously described.

Possible response:
    - "QUERY":  
    Questions that request data analysis based on "CloudTrail" or "GuardDuty" logs.  
    These questions typically require SQL generation to query structured logs.  
    Example patterns:
        • Who accessed S3 yesterday?  
        • Show login failures in the last 24 hours  
        • What user deleted EC2 instances recently?  
    MUST involve:  
        - eventName, sourceIPAddress, userIdentity, region, or timestamp  
        - keywords like: find, show, list, get, analyze, from logs  

    - "DOCUMENT":  
    Questions that ask for explanations, descriptions, or definitions of AWS-related services, fields, concepts, or syntax.  
    These questions do not require data querying, but rather reference AWS documentation.  
    Example patterns:  
        • What does GuardDuty severity mean?  
        • How does partitioning work in Athena?  
        • Explain sourceIPAddress in CloudTrail  
    May include:  
        - questions starting with what / how / why / explain  
        - terminology clarification (e.g., difference between LIMIT and OFFSET)

- "CLOUDWATCH": Questions to run CloudWatch Logs Insights query directly

- "USELESS":  
    Questions that are irrelevant to AWS log analysis or documentation.  
    This includes greetings, personal opinions, jokes, or off-topic inquiries.  
    Example patterns:  
        • Hello  
        • Who made you?  
        • Tell me a joke  
        • I love AWS

질문: {user_question}

응답 (QUERY, DOCUMENT, CLOUDWATCH, USELESS만 작성):
"""

    classification_result = invoke_bedrock_nova(classification_prompt)
    decision = classification_result["output"]["message"]["content"][0]["text"].strip()
    print(f"분류 결과: {decision}")

    text_answer_content = ""
    response_data = {} # 최종 응답 데이터를 담을 딕셔너리

    # 2단계: 분류 결과에 따라 적절한 서비스로 라우팅
    if "QUERY" in decision:
        prompt = build_llm1_prompt(user_question) # 이 함수는 llm_service 내에 정의되어 있어야 합니다.
        sql_query_response = invoke_bedrock_nova(prompt)
        raw_text_sql = sql_query_response["output"]["message"]["content"][0]["text"]
        cleaned_sql_query = ""
        query_execution_result = "###IGNORED###" # 기본값 설정

        if is_ignored(raw_text_sql): # is_ignored 함수 필요
            query_execution_result = "###IGNORED###"
            text_answer_content = "죄송합니다. 요청하신 질문에 대한 SQL 쿼리 생성이 적절하지 않아 처리할 수 없습니다."
            cleaned_sql_query = "N/A (생성되지 않음)"
        else:
            cleaned_sql_query = raw_text_sql.strip().removeprefix("```sql").removesuffix("```").strip()
            call_create_table_cloudtrail() # 이 함수는 llm_service 내에 정의되어 있어야 합니다.
            call_create_table_guardduty() # 이 함수는 llm_service 내에 정의되어 있어야 합니다.
            query_execution_result = call_execute_query(cleaned_sql_query) # 이 함수는 llm_service 내에 정의되어 있어야 합니다.
        
        # 쿼리 결과가 IGNORED가 아닐 때만 LLM2 호출
        if query_execution_result != "###IGNORED###":
            llm2_response = requests.post(
                f"{CONFIG['api']['endpoint']}/llm2",
                json={
                    "question": user_question,
                    "result": query_execution_result
                }
            )
            try:
                llm2_answer_json = llm2_response.json()
                llm2_answer = llm2_answer_json.get("answer", "[답변 생성 실패]")
                if isinstance(llm2_answer, str):
                    text_answer_content = llm2_answer
                else:
                    text_answer_content = llm2_answer.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "[답변 없음]")
            except Exception as parse_error:
                print("LLM2 응답 파싱 실패 (QUERY):", str(parse_error))
                text_answer_content = "[답변 파싱 실패]"
        
        response_data = {
            "answer": text_answer_content,
            "query_string": cleaned_sql_query,
            "query_result": query_execution_result
        }

    elif "DOCUMENT" in decision:
        mcp_response = call_mcp_service(user_question) # 이 함수는 llm_service 내에 정의되어 있어야 합니다.
        text_answer_content = mcp_response.get("result", "[MCP 응답 없음]")
        # 문서 검색 결과는 보통 번역이 필요할 수 있습니다. (기존 로직에 trans_eng_to_kor가 있다면 사용)
        # text_answer_content = trans_eng_to_kor(text_answer_content) # 필요시 주석 해제
        response_data = {"answer": text_answer_content}

    elif "CLOUDWATCH" in decision:
        insights_generation_result = generate_insights_query(user_question) # 이 함수는 llm_service 내에 정의되어 있어야 합니다.
        insights_query_string = insights_generation_result.get("query", "###IGNORED###")
        log_group_name = insights_generation_result.get("log_group")
        query_execution_result = None

        if insights_query_string == "###IGNORED###" or not log_group_name:
            text_answer_content = "죄송합니다. 이 시스템은 AWS 보안 로그 관련 질문에만 답변합니다."
            response_data = {
                "answer": text_answer_content,
                "query_string": "N/A (생성되지 않음)",
                "query_result": "N/A (실행되지 않음)"
            }
        else:
            try:# 이 함수는 llm_service 내에 정의되어 있어야 합니다.
                query_execution_result = call_insights_query( 
                    log_group=log_group_name,
                    query_string=insights_query_string,
                    start_time=int((time.time() - 7 * 24 * 3600) * 1000),  # 지난 7일
                    end_time=int(time.time() * 1000)
                )
                query_list = []
                for result in query_execution_result:
                    query_list.append({item['field']: item['value'] for item in result})
                print(">>> 쿼리 결과:", query_list)
                llm2_response = requests.post(
                    f"{CONFIG['api']['endpoint']}/llm2",
                    json={
                        "question": user_question,
                        "result": query_execution_result
                    }
                )
                print(">>> llm2 status (CLOUDWATCH):", llm2_response.status_code)
                print(">>> llm2 body (CLOUDWATCH):", llm2_response.text)
                try:
                    llm2_answer_json = llm2_response.json()
                    llm2_answer = llm2_answer_json.get("answer", "[답변 생성 실패]")
                    if isinstance(llm2_answer, str):
                        text_answer_content = llm2_answer
                    else:
                        text_answer_content = llm2_answer.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "[답변 없음]")
                except Exception as parse_error:
                    print("LLM2 응답 파싱 실패 (CLOUDWATCH):", str(parse_error))
                    text_answer_content = "[답변 파싱 실패]"
            except Exception as e:
                print(f"CloudWatch 쿼리 실행 또는 LLM2 호출 실패: {str(e)}")
                text_answer_content = "CloudWatch 쿼리 실행 중 오류가 발생했습니다."
                # 오류 발생 시에도 query_result는 None일 수 있으므로 그대로 전달
            
            response_data = {
                "answer": text_answer_content,
                "query_string": insights_query_string, 
                "query_result": query_list
            }
    else: # USELESS 또는 기타
        text_answer_content = "죄송합니다. 이 시스템은 AWS 운영정보 혹은 메뉴얼 관련 질문에만 답변합니다."
        response_data = {"answer": text_answer_content}

    # 최종 결과를 Slack으로 전송 (주석 처리된 부분)
    # try:
    #     #send_slack_dm(slack_user_id, f"🧠 분석 결과:\n{text_answer_content}")
    #     print(1)
    # except Exception as e:
    #     print(f"Slack 전송 실패: {str(e)}")
    #     # text_answer_content += "\n(Slack 전송 실패)" # 필요에 따라 오류 메시지 추가

    response_time = datetime.now(timezone.utc) # 응답 생성 시간
    elapsed = response_time - question_time
    minutes, seconds = divmod(elapsed.total_seconds(), 60)
    elapsed_str = f"{int(minutes)}분 {int(seconds)}초" if minutes else f"{int(seconds)}초"

    # response_data에 소요 시간 추가
    response_data["elapsed_time"] = elapsed_str
    # "status"는 일관성을 위해 최상위 레벨에 유지 (기존 코드 방식)
    final_response_payload = {
        "status": "질문 처리 완료",
        **response_data # response_data의 모든 키-값을 여기에 펼쳐 넣음
    }

    return cors_response(200, final_response_payload, origin)

def handle_llm2_request(body, CONFIG, origin):
    user_question = body.get("question")
    query_result = body.get("result")

    if not user_question or not query_result:
        return cors_response(400, {"error": "request body에 'question' 이나 'result'가 없음."}, origin)

    prompt = build_llm2_prompt(user_question, query_result)
    answer = invoke_bedrock_nova(prompt)
    return cors_response(200, {"answer": answer}, origin)