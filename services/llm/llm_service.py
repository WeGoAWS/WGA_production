import json
import urllib.parse
import requests
import boto3
import os
from datetime import datetime, timezone
from common.config import get_config
from common.utils import invoke_bedrock_nova, cors_headers, cors_response
from slack_sdk import WebClient

# Lambda 환경에서 효율적인 재사용을 위한 클라이언트 캐싱
client = None


def get_client():
    """
    MCP 클라이언트 인스턴스를 가져오거나 생성
    Lambda 콜드 스타트 최적화를 위해 전역 변수로 재사용
    """
    global client
    if client is None:
        # 환경 변수에서 구성 가져오기
        CONFIG = get_config()
        mcp_url = os.environ.get('MCP_URL') or CONFIG.get('mcp', {}).get('function_url')

        # 사용할 클라이언트 유형 결정 (Bedrock 또는 Anthropic)
        use_anthropic = os.environ.get('USE_ANTHROPIC_API', 'true').lower() == 'true'

        if use_anthropic:
            # Anthropic API 설정
            anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY') or CONFIG.get('anthropic', {}).get('api_key')
            model_id = os.environ.get('ANTHROPIC_MODEL_ID', 'claude-3-5-sonnet-20241022')

            # Anthropic 클라이언트 초기화
            from mcp_anthropic_client import AnthropicMCPClient
            client = AnthropicMCPClient(
                mcp_url=mcp_url,
                api_key=anthropic_api_key,
                model_id=model_id
            )
        else:
            # Bedrock 설정
            mcp_token = os.environ.get('MCP_TOKEN', '')
            region = os.environ.get('AWS_REGION', 'us-east-1')
            model_id = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')

            # Bedrock 클라이언트 초기화
            from mcp_bedrock_client import BedrockMCPClient
            client = BedrockMCPClient(
                mcp_url=mcp_url,
                region=region,
                auth_token=mcp_token,
                model_id=model_id
            )

        # 세션 초기화 및 도구 로드
        client.initialize()

    return client


def handle_llm1_with_mcp(body, origin):
    """
    MCP 클라이언트를 사용하여 llm1 요청을 처리

    Args:
        body: 요청 본문
        origin: CORS origin

    Returns:
        응답 객체
    """
    try:
        # 사용자 입력 추출
        user_input = body.get('question') or body.get('text') or body.get('input', {}).get('text', '')
        if not user_input:
            return cors_response(400, {"error": "사용자 입력이 제공되지 않았습니다."}, origin)

        # 시스템 프롬프트 설정
        system_prompt = """You are a friendly assistant that is responsible for resolving user queries.
            Follow <User Query Determination> first. If you need instruction, follow proper <Instructions> afterwards. Before generating final answer, follow <Final Answer Format>.
            
            <User Query Determination>
                - Always treat time information based on UTC+9(Seoul). If not, convert time using tools related to time_mcp_client.
                - If you determine user query related to analyzing AWS resources(not cost explorer), follow monitoring agent instructions.
                - If you determine user query related to cost explorer, follow monitoring agent instructions.
                - If you determine user query related to AWS Document, use tools related to document_mcp_client.
            
            <Intructions for cost explorer agent>
                You are the monitoring agent responsible for analyzing costs for using AWS service. Your tasks include:
                    - Always use get_detailed_breakdown_by_day first.
                    - When using get_detailed_breakdown_by_day, parameters should be like params[{"days": 30}].
            
            <Intructions for monitoring agent>
                You are the monitoring agent responsible for analyzing AWS resources, including CloudWatch logs, alarms, and dashboards. You must follow guidelines as well. Your tasks include:
    
                1. **List Available CloudWatch Dashboards:**
                   - Utilize the `list_cloudwatch_dashboards` tool to retrieve a list of all CloudWatch dashboards in the AWS account.
                   - Provide the user with the names and descriptions of these dashboards, offering a brief overview of their purpose and contents.
            
                2. **Fetch Recent CloudWatch Logs for Requested Services:**
                   - When a user specifies a service (e.g., EC2, Lambda, RDS), use the `fetch_cloudwatch_logs_for_service` tool to retrieve the most recent logs for that service.
                   - Analyze these logs to identify any errors, warnings, or anomalies.
                   - Summarize your findings, highlighting any patterns or recurring issues, and suggest potential actions or resolutions.
            
                3. **Retrieve and Summarize CloudWatch Alarms:**
                   - If the user inquires about alarms or if log analysis indicates potential issues, use the `get_cloudwatch_alarms_for_service` tool to fetch relevant alarms.
                   - Provide details about active alarms, including their state, associated metrics, and any triggered thresholds.
                   - Offer recommendations based on the alarm statuses and suggest possible remediation steps.
            
                4. **Analyze Specific CloudWatch Dashboards:**
                   - When a user requests information about a particular dashboard, use the `get_dashboard_summary` tool to retrieve and summarize its configuration.
                   - Detail the widgets present on the dashboard, their types, and the metrics or logs they display.
                   - Provide insights into the dashboard's focus areas and how it can be utilized for monitoring specific aspects of the AWS environment.
                
                5. **List and Explore CloudWatch Log Groups:**
                   - Use the `list_log_groups` tool to retrieve all available CloudWatch log groups in the AWS account.
                   - Help the user navigate through these log groups and understand their purpose.
                   - When a user is interested in a specific log group, explain its contents and how to extract relevant information.
                   - Use correct prefix. Filter like Service Log Prefixes.
                   
               6. **Analyze Specific Log Groups in Detail:**
                   - When a user wants to gain insights about a specific log group, use the `analyze_log_group` tool.
                   - Summarize key metrics like event count, error rates, and time distribution.
                   - Identify common patterns and potential issues based on log content.
                   - Provide actionable recommendations based on the observed patterns and error trends.
                
                **Guidelines:**
            
                    - Always begin by listing the available CloudWatch dashboards to inform the user of existing monitoring setups.
                    - When analyzing logs or alarms, be thorough yet concise, ensuring clarity in your reporting.
                    - Avoid making assumptions; base your analysis strictly on the data retrieved from AWS tools.
                    - Clearly explain the available AWS services and their monitoring capabilities when prompted by the user.
                    - Use correct prefix. Filter like Service Log Prefixes.
            
                **Available AWS Services for Monitoring:**
            
                    - **EC2/Compute Instances** [ec2]
                    - **Lambda Functions** [lambda]
                    - **RDS Databases** [rds]
                    - **EKS Kubernetes** [eks]
                    - **API Gateway** [apigateway]
                    - **CloudTrail** [cloudtrail]
                    - **S3 Storage** [s3]
                    - **VPC Networking** [vpc]
                    - **WAF Web Security** [waf]
                    - **Bedrock** [bedrock/generative AI]
                    - **IAM Logs** [iam] (Use this option when users inquire about security logs or events.)
                    
                **Service Log Prefixes**
                    "ec2": ["/aws/ec2", "/var/log"],
                    "lambda": ["/aws/lambda"],
                    "rds": ["/aws/rds"],
                    "eks": ["/aws/eks"],
                    "apigateway": ["/aws/apigateway"],
                    "cloudtrail": ["/aws/cloudtrail"],
                    "s3": ["/aws/s3", "/aws/s3-access"],
                    "vpc": ["/aws/vpc"],
                    "waf": ["/aws/waf"],
                    "bedrock": [f"/aws/bedrock/modelinvocations"],
                    "iam": ["/aws/dummy-security-logs"]
                
                Your role is to assist users in monitoring and analyzing their AWS resources effectively, providing actionable insights based on the data available.
            
            <Final Answer Format>
                - You must answer in korean, even though the question was in foreign language.
        """

        # MCP 클라이언트 가져오기
        client = get_client()

        # 사용자 입력 처리
        question_time = datetime.now(timezone.utc)
        response_text = client.process_user_input(user_input, system_prompt)
        response_time = datetime.now(timezone.utc)

        # 경과 시간 계산
        elapsed = response_time - question_time
        minutes, seconds = divmod(elapsed.total_seconds(), 60)
        elapsed_str = f"{int(minutes)}분 {int(seconds)}초" if minutes else f"{int(seconds)}초"

        # 성공 응답 반환
        return cors_response(200, {
            "answer": response_text,
            "elapsed_time": elapsed_str

        }, origin)

    except Exception as e:
        return cors_response(500, {
            "error": "MCP 처리 중 오류 발생",
            "answer": str(e)
        }, origin)



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
    # 레지스트리에 정보가 있는지 확인
    if "cloudtrail" in registry and "guardduty" in registry:
        ct_table = registry["cloudtrail"]["table_name"]
        ct_location = registry["cloudtrail"]["s3_path"]
        gd_table = registry["guardduty"]["table_name"]
        gd_location = registry["guardduty"]["s3_path"]

        # 테이블 정보를 프롬프트에 명시적으로 포함
        tables_info = f"""
Available tables:
1. {ct_table} - CloudTrail logs at {ct_location}
2. {gd_table} - GuardDuty logs at {gd_location}
        """
    else:
        # 테이블 정보가 없는 경우에 대한 기본값
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
    res = requests.post(f'{CONFIG['api']['endpoint']}/execute-query',
                        json=wrapper_payload)  # Athena 쿼리 실행 API URL을 여기에 입력하세요
    return res.json()


def send_slack_dm(user_id, message):
    CONFIG = get_config()
    client = WebClient(token=CONFIG['slackbot']['token'])  # 여기에 Slack Bot Token

    response = client.chat_postMessage(
        channel=user_id,  # 여기서 user_id 그대로 DM 채널로 사용 가능
        text=message
    )
    if not response["ok"]:
        print("❌ Slack 메시지 실패 사유:", response["error"])
    return response


def handle_llm1_request(body, CONFIG, origin):
    question_time = datetime.now(timezone.utc)
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

    - "Boundary":
    Questions that are borderline between "QUERY" and "DOCUMENT".
    These questions may require both data querying and documentation reference. 

    - "USELESS":  
    Questions that are irrelevant to AWS log analysis or documentation.  
    This includes greetings, personal opinions, jokes, or off-topic inquiries.  
    Example patterns:  
        • Hello  
        • Who made you?  
        • Tell me a joke  
        • I love AWS


    Questions: {user_question}

    Result(QUERY, DOCUMENT, BOUNDARY, or USELESS only):
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

        # 코드 블록 마커 제거
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
                text_answer = llm2_answer.get("output", {}).get("message", {}).get("content", [{}])[0].get("text",
                                                                                                           "[답변 없음]")
        except Exception as parse_error:
            print("응답 파싱 실패:", str(parse_error))
            text_answer = "[답변 파싱 실패]"

    elif "DOCUMENT" in decision:  # "DOCUMENT"인 경우
        # MCP Lambda 호출
        mcp_response = call_mcp_service(user_question)
        text_answer = mcp_response.get("result", "[MCP 응답 없음]")
        text_answer = trans_eng_to_kor(text_answer)

    elif "BOUNDARY" in decision:
        # 기존 로직: SQL 쿼리 생성 및 실행
        prompt = build_llm1_prompt(user_question)
        sql_query = invoke_bedrock_nova(prompt)
        raw_text = sql_query["output"]["message"]["content"][0]["text"]

        # 코드 블록 마커 제거
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
                text_answer_q = llm2_answer
            else:
                text_answer_q = llm2_answer.get("output", {}).get("message", {}).get("content", [{}])[0].get("text",
                                                                                                             "[답변 없음]")
        except Exception as parse_error:
            print("응답 파싱 실패:", str(parse_error))
            text_answer_q = "[답변 파싱 실패]"

        # MCP Lambda 호출
        mcp_response = call_mcp_service(user_question)
        text_answer_d = mcp_response.get("result", "[MCP 응답 없음]")
        text_answer_d = trans_eng_to_kor(text_answer_d)

        text_answer = f"""
        [1] 📊 로그 분석 결과:
        {text_answer_q}

        [2] 📘 공식 문서 기반 설명:
        {text_answer_d}
        """

    else:
        text_answer = "죄송합니다. 이 시스템은 AWS 운영정보 혹은 메뉴얼 관련 질문에만 답변합니다."
    # 최종 결과를 Slack으로 전송
    # send_slack_dm(slack_user_id, f"🧠 분석 결과:\n{text_answer}")

    response_time = datetime.now(timezone.utc)
    elapsed = response_time - question_time
    minutes, seconds = divmod(elapsed.total_seconds(), 60)
    # 포맷
    elapsed_str = f"{int(minutes)}분 {int(seconds)}초" if minutes else f"{int(seconds)}초"

    return cors_response(200, {
        "status": "질문 처리 완료",
        "answer": text_answer + f"\n\n소요시간: {elapsed_str}"
    }, origin)


def handle_llm2_request(body, CONFIG, origin):
    user_question = body.get("question")
    query_result = body.get("result")

    if not user_question or not query_result:
        return cors_response(400, {"error": "request body에 'question' 이나 'result'가 없음."}, origin)

    prompt = build_llm2_prompt(user_question, query_result)
    answer = invoke_bedrock_nova(prompt)

    return cors_response(200, {"answer": answer}, origin)

