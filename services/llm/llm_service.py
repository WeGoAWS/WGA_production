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

# DynamoDB 설정 (안전하게 초기화)
try:
    CONFIG = get_config()
    CHAT_HISTORY_TABLE = CONFIG.get('db', {}).get('chat_history_table')

    if CHAT_HISTORY_TABLE:
        dynamodb = boto3.resource('dynamodb')
        chat_table = dynamodb.Table(CHAT_HISTORY_TABLE)
        print(f"DynamoDB 테이블 연결 성공: {CHAT_HISTORY_TABLE}")
    else:
        chat_table = None
        print("DynamoDB 테이블 설정이 없습니다. 캐싱 기능을 비활성화합니다.")
except Exception as e:
    print(f"DynamoDB 초기화 오류: {str(e)}")
    chat_table = None


def get_anthropic_models():
    """
    Anthropic API에서 사용 가능한 모델 목록을 조회

    Returns:
        list: 모델 정보 배열 (display_name과 id만 포함)
    """
    try:
        CONFIG = get_config()
        anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY') or CONFIG.get('anthropic', {}).get('api_key')

        if not anthropic_api_key:
            print("Anthropic API 키가 설정되지 않았습니다.")
            return []

        headers = {
            "x-api-key": anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        response = requests.get(
            "https://api.anthropic.com/v1/models",
            headers=headers
        )

        if response.status_code != 200:
            print(f"Anthropic Models API 오류: {response.status_code} - {response.text}")
            return []

        models_data = response.json()
        models = models_data.get('data', [])

        # display_name과 id만 추출하여 배열로 반환
        model_list = []
        for model in models:
            model_info = {
                "id": model.get("id", ""),
                "display_name": model.get("display_name", model.get("id", ""))
            }
            model_list.append(model_info)

        print(f"Anthropic 모델 {len(model_list)}개 조회 완료")
        return model_list

    except Exception as e:
        print(f"Anthropic 모델 조회 중 오류: {str(e)}")
        return []


def get_session_messages_as_array(session_id: str) -> list:
    """
    DynamoDB에서 세션의 메시지 히스토리를 messages 배열 형식으로 가져옴

    Args:
        session_id: 채팅 세션 ID

    Returns:
        messages 배열 형식의 대화 기록
    """
    try:
        if not chat_table:
            print("DynamoDB 테이블이 초기화되지 않았습니다.")
            return []

        response = chat_table.get_item(
            Key={'sessionId': session_id}
        )

        session = response.get('Item')
        if not session:
            print(f"세션을 찾을 수 없습니다: {session_id}")
            return []

        messages = session.get('messages', [])

        # 메시지를 시간순으로 정렬
        messages.sort(key=lambda x: x.get('timestamp', ''))

        # Claude/Anthropic API 형식으로 변환
        formatted_messages = []
        for msg in messages:
            sender = msg.get('sender', 'user')
            text = msg.get('text', '')

            if sender == 'user':
                formatted_messages.append({
                    "role": "user",
                    "content": text
                })
            elif sender == 'assistant':
                formatted_messages.append({
                    "role": "assistant",
                    "content": text
                })

        print(f"세션 {session_id}에서 {len(formatted_messages)}개 메시지를 배열 형식으로 로드됨")
        return formatted_messages

    except Exception as e:
        print(f"세션 메시지 조회 실패: {str(e)}")
        return []


def get_client(model_id: str = None):
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
    MCP 클라이언트를 사용하여 llm1 요청을 처리하고 도구 사용 과정 및 결과 포함
    세션 기반 메시지 캐싱 지원 (개선된 messages 배열 방식)

    Args:
        body: 요청 본문
        origin: CORS origin

    Returns:
        응답 객체 (도구 사용 과정 및 결과 포함)
    """
    try:
        # 요청 데이터 추출
        user_input = body.get('question') or body.get('text') or body.get('input', {}).get('text', '')
        session_id = body.get('sessionId')
        is_cached = body.get('isCached', True)
        model_id = body.get('modelId')
        slack_user_id = body.get("user_id")

        print(f"=== 요청 분석 ===")
        print(f"user_input: {user_input}")
        print(f"session_id: {session_id}")
        print(f"is_cached: {is_cached}")
        print(f"model_id: {model_id}")
        print(f"chat_table 상태: {chat_table is not None}")
        print(f"전체 body: {json.dumps(body, ensure_ascii=False)}")

        if not user_input:
            return cors_response(400, {"error": "사용자 입력이 제공되지 않았습니다."}, origin)

        # Slack에 대기 메시지 전송
        if slack_user_id:
            send_slack_dm(slack_user_id, "⏳ 분석중입니다... 조금만 기다려주세요!")

        # 시스템 프롬프트 설정
        system_prompt = """You are name is "AWS Cloud Agent" and you are an AI assistant specialized in AWS services, monitoring, and documentation. Your primary goal is to help users with their AWS-related questions and tasks, but you should also engage in natural conversation when users interact with you casually.

        CRITICAL INSTRUCTION: When processing user requests with conversation history, focus primarily on providing a comprehensive final answer based on the most recent user message, while using the conversation context only as supporting background information. Do not repeatedly search for the same information or get stuck in tool-calling loops.

        <Context Analysis>
        CRITICAL: Always analyze conversation context before selecting tools, but prioritize generating a final answer over endless information gathering.

        Previous Conversation Context:
        - Review the conversation history to understand the current topic and user intent
        - Identify what the user was previously asking about (IAM security, cost analysis, documentation, etc.)
        - Determine if the current request is a continuation of the previous topic

        Continuation Pattern Detection:
        - If user says phrases like "기간을 한달로 해서", "다시 검색해줘", "기간 변경해서", "더 길게/짧게", this indicates they want to modify parameters of the SAME previous query
        - Extract time/period parameters: "한달/한 달" = 30 days, "일주일" = 7 days, "3일" = 3 days
        - DO NOT change the topic/category - continue with the same type of analysis but with new parameters

        Tool Category Consistency:
        - IAM/Security topics → Use only: fetch_cloudwatch_logs_for_service, get_cloudwatch_alarms_for_service
        - Cost Analysis topics → Use only: get_detailed_breakdown_by_day, cost-related tools
        - Documentation topics → Use only: search_documentation, read_documentation
        - NEVER mix categories - if previous conversation was about IAM security, don't suddenly use cost analysis tools

        Parameter Modification Rules:
        - When user requests parameter changes (like time period), apply them to the SAME tool category as before
        - Example: Previous query about "IAM 정책" + user says "기간을 한달로" → Use IAM tools with days=30, NOT cost tools

        IMPORTANT: If you have sufficient information from previous context or initial tool calls to answer the user's question, provide a comprehensive final answer instead of making additional tool calls.
        </Context Analysis>

        <User Query Determination>
        Always treat time information based on UTC+9(Seoul). If not, convert time using tools related to time_mcp_client.

        For questions about user access, logins, or "who accessed/connected today", ALWAYS use the fetch_cloudwatch_logs_for_service tool with "cloudtrail" as the service parameter to check CloudTrail logs directly. DO NOT respond that logs are unavailable without checking first.

        Context-Aware Decision Making:
        - If continuing previous IAM/security topic: follow monitoring agent instructions with security focus
        - If continuing previous cost topic: follow cost explorer agent instructions  
        - If continuing previous documentation topic: use document_mcp_client tools
        - If new topic: determine based on current message content

        Tool Usage Priority:
        1. If you determine user query related to analyzing AWS resources(not cost explorer), follow monitoring agent instructions
        2. If you determine user query related to cost explorer, follow cost explorer agent instructions
        3. If you determine user query related to AWS Document, use tools related to document_mcp_client
        4. If the user's message appears to be casual conversation (greetings, small talk, personal questions), respond in a friendly, conversational manner

        CRITICAL: After gathering initial information through tool calls, focus on synthesizing a comprehensive final answer rather than making additional tool calls for similar information.
        </User Query Determination>

        <Instructions for cost explorer agent>
        You are the monitoring agent responsible for analyzing costs for using AWS service. Your tasks include:

        - Always use get_detailed_breakdown_by_day first
        - When using get_detailed_breakdown_by_day, parameters should be like params[{"days": 30}]
        - Present cost information clearly with trends and recommendations
        - After getting cost data, provide analysis and recommendations without additional tool calls unless absolutely necessary
        </Instructions for cost explorer agent>

        <Instructions for monitoring agent>
        You are the monitoring agent responsible for analyzing AWS resources, including CloudWatch logs, alarms, and dashboards. Your tasks include:

        Context-Aware Tool Selection:
        - For IAM/Security queries (including policy violations, permissions, access controls):
          * Primary tool: fetch_cloudwatch_logs_for_service with service="cloudtrail"
          * Secondary tool: get_cloudwatch_alarms_for_service with service="iam"
          * Apply time parameters (days) to these tools when specified
          * Use appropriate filter patterns for IAM events: "CreatePolicy", "UpdatePolicy", "PutUserPolicy", "PutRolePolicy", "AttachRolePolicy", etc.

        Efficient Tool Usage:
        1. List Available CloudWatch Dashboards (if relevant to query)
        2. Fetch Recent CloudWatch Logs for Requested Services (maximum 1-2 calls per service)
        3. Retrieve CloudWatch Alarms (if indicated by logs or user request)
        4. Analyze results and provide comprehensive answer

        CRITICAL: Do not make repetitive tool calls. If you've already gathered relevant information, synthesize it into a final answer.

        For access/login related queries:
        - ALWAYS check CloudTrail logs first using fetch_cloudwatch_logs_for_service with "cloudtrail" parameter
        - Look for events like "ConsoleLogin", "AssumeRole", or other access-related events
        - Extract usernames, IP addresses, and timestamps from CloudTrail logs
        - If no logs are found after ONE search, explain that you've checked CloudTrail but couldn't find access records

        Guidelines:
        - CRITICAL: Maintain topic consistency - if previous conversation was about IAM/security, continue with security-focused tools even when user modifies parameters
        - For access/login related queries, check CloudTrail logs ONCE before suggesting configuration changes
        - Always begin by listing available CloudWatch dashboards only if relevant to the user's specific query
        - When analyzing logs or alarms, be thorough yet concise, ensuring clarity in your reporting
        - Avoid making assumptions; base your analysis strictly on the data retrieved from AWS tools
        - Use correct prefix and filters for Service Log Prefixes
        - Never say logs are unavailable without first checking them using the appropriate tools
        - STOP making additional tool calls once you have sufficient information to answer the user's question

        Available AWS Services for Monitoring:
        EC2/Compute Instances [ec2], Lambda Functions [lambda], RDS Databases [rds], EKS Kubernetes [eks], API Gateway [apigateway], CloudTrail [cloudtrail], S3 Storage [s3], VPC Networking [vpc], WAF Web Security [waf], Bedrock [bedrock/generative AI], Guardduty [guardduty], IAM Logs [iam]

        Service Log Prefixes: 
        "ec2": ["/aws/ec2", "/var/log"], "lambda": ["/aws/lambda"], "rds": ["/aws/rds"], "eks": ["/aws/eks"], "apigateway": ["API-Gateway-Execution-Logs_", "/aws/apigateway"], "cloudtrail": ["/aws/cloudtrail"], "s3": ["/aws/s3", "/aws/s3-access"], "vpc": ["/aws/vpc"], "waf": ["/aws/waf"], "bedrock": ["/aws/bedrock/modelinvocations"], "iam": ["/aws/dummy-security-logs"], "guardduty": ["/aws/guardduty"]
        </Instructions for monitoring agent>

        <Instructions for casual conversation>
        When users engage in casual conversation (greetings, small talk, personal questions), respond naturally:

        Warm and Helpful Tone:
        - Maintain a friendly, conversational style
        - Keep responses concise but personable
        - Use natural language patterns rather than technical format

        Contextual Awareness:
        - Recognize greetings like "hello," "hi," or "안녕" and respond appropriately
        - For vague requests, offer general help with AWS services while keeping it conversational
        - When the conversation shifts between casual and technical, adapt your tone accordingly

        Balanced Response Format:
        - For casual queries, avoid overly structured responses (like numbered lists)
        - Limit technical jargon unless the conversation has shifted to technical topics
        - Prioritize natural dialogue flow over comprehensive information dumps
        </Instructions for casual conversation>

        <Final Answer Guidelines>
        CRITICAL: Focus on providing comprehensive final answers rather than endless tool calling.

        Response Strategy:
        1. If you have conversation history that provides relevant context, use it to inform your answer
        2. Make targeted tool calls only when absolutely necessary for new or updated information
        3. Once you have sufficient information, synthesize a complete answer without additional tool calls
        4. Prioritize the user's most recent question while incorporating relevant historical context

        Answer Format:
        - You must answer in Korean, regardless of the language of the question
        - Balance helpfulness with conversational flow
        - Avoid unnecessarily formal or technical language for casual exchanges
        - For casual interactions, respond briefly and conversationally like a helpful friend
        - If you're unsure whether the user is asking about AWS or having casual conversation, favor the casual interpretation
        - Keep your initial response brief, then clarify how you can help with AWS services
        - Avoid presenting extensive capabilities lists unless specifically asked

        Remember: The goal is to provide helpful, accurate information efficiently. Use conversation history as context, but focus on delivering a comprehensive final answer to the user's current question without getting stuck in repetitive information gathering loops.

        <Rate Limit Prevention>
        - Use tools efficiently to avoid rate limits and infinite loops
        - Limit response tokens to prevent excessive API usage
        - When tool results are large, summarize key points instead of including full responses
        - Prioritize the most relevant tools for the user's question
        - STOP tool calling once you have enough information to provide a good answer
        - If you find yourself making the same tool call repeatedly, STOP and provide an answer based on available information
        """

        # MCP 클라이언트 가져오기
        client = get_client(model_id)

        # 사용자 입력 처리 시작 시간 기록
        question_time = datetime.now(timezone.utc)

        # 세션 기반 처리 (개선된 방식 - messages 배열 사용)
        if is_cached and session_id and chat_table:
            try:
                print(f"=== 세션 캐싱 모드 시작 (개선된 방식) ===")
                print(f"세션 ID: {session_id}")

                # 세션 메시지 히스토리를 messages 배열로 로드
                previous_messages = get_session_messages_as_array(session_id)

                if previous_messages:
                    print(f"=== 히스토리 발견 ===")
                    print(f"로드된 메시지 수: {len(previous_messages)}")

                    # 메시지 샘플 출력 (디버깅용)
                    for i, msg in enumerate(previous_messages[-3:]):  # 마지막 3개만
                        print(f"최근 메시지 {i + 1}: {msg.get('role')} - {msg.get('content', '')[:50]}...")

                    # 이전 대화 + 새 사용자 입력으로 처리
                    response_text = client.process_user_input_with_history(
                        user_input,
                        system_prompt,
                        previous_messages
                    )
                else:
                    print("=== 세션 메시지 없음 ===")
                    print("일반 모드로 처리")
                    response_text = client.process_user_input(user_input, system_prompt)

            except Exception as e:
                print(f"=== 세션 캐싱 오류 ===")
                print(f"오류: {str(e)}")
                print("일반 모드로 폴백")
                response_text = client.process_user_input(user_input, system_prompt)
        else:
            # 일반 처리 (기존 방식)
            print("=== 일반 모드 ===")
            print(f"is_cached: {is_cached}, session_id: {session_id}, chat_table: {chat_table is not None}")
            response_text = client.process_user_input(user_input, system_prompt)

        # 디버그 로그 가져오기 (추가된 get_debug_log 메서드 사용)
        debug_log = client.get_debug_log() if hasattr(client, "get_debug_log") else []

        # 도구 사용 및 사고 과정 정리
        tools_used = []
        reasoning_steps = []
        token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        for entry in debug_log:
            entry_type = entry.get("type")

            if entry_type == "model_reasoning":
                reasoning_steps.append({
                    "content": entry.get("content"),
                    "input_tokens": entry.get("input_tokens", 0),
                    "output_tokens": entry.get("output_tokens", 0),
                    "timestamp": entry.get("timestamp")
                })
            elif entry_type == "tool_result":
                tools_used.append({
                    "tool_name": entry.get("tool_name"),
                    "input": entry.get("input"),
                    "output": entry.get("output"),
                    "timestamp": entry.get("timestamp")
                })
            elif entry_type in ["final_response", "final_response_with_history"]:
                # 최종 응답에서 총 토큰 사용량 추출
                token_usage = {
                    "input_tokens": entry.get("input_tokens", 0),
                    "output_tokens": entry.get("output_tokens", 0),
                }
                print(f"최종 토큰 사용량 추출: {token_usage}")

        # 시간 순으로 정렬
        reasoning_steps.sort(key=lambda x: x.get("timestamp", 0))
        tools_used.sort(key=lambda x: x.get("timestamp", 0))

        # 타임스탬프 정보는 제거
        for step in reasoning_steps:
            if "timestamp" in step:
                del step["timestamp"]

        for tool in tools_used:
            if "timestamp" in tool:
                del tool["timestamp"]

        # tools_used에서 output이 null인 것들 제거
        tools_used = [tool for tool in tools_used if tool.get("output") is not None]

        reasoning_content = []
        for step in reasoning_steps:
            reasoning_content.append({
                "content": step.get("content"),
                "input_tokens": step.get("input_tokens", 0),
                "output_tokens": step.get("output_tokens", 0)
            })

        debug_info = {
            "tools_used": tools_used,
            "reasoning": reasoning_content,
            "session_cached": is_cached and session_id is not None and chat_table is not None,
            "session_id": session_id if is_cached else None,
            "token_usage": token_usage
        }

        # 응답 시간 기록 및 경과 시간 계산
        response_time = datetime.now(timezone.utc)
        elapsed = response_time - question_time
        minutes, seconds = divmod(elapsed.total_seconds(), 60)
        elapsed_str = f"{int(minutes)}분 {int(seconds)}초" if minutes else f"{int(seconds)}초"

        # 최종 결과를 Slack으로 전송
        if slack_user_id:
            send_slack_dm(slack_user_id, f"🧠 분석 결과:\n{response_text}")

        # 성공 응답 반환 (도구 사용 과정 및 결과 포함)
        return cors_response(200, {
            "answer": response_text,
            "elapsed_time": elapsed_str,
            "inference": debug_info  # 디버그 정보 추가
        }, origin)

    except Exception as e:
        print(f"MCP 처리 중 오류: {str(e)}")
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