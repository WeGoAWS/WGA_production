import json
import urllib.parse
import requests
import boto3
import os
from common.config import get_config
from common.utils import invoke_bedrock_nova, cors_headers, cors_response
from slack_sdk import WebClient

def get_table_registry():
    dynamodb = boto3.resource("dynamodb")
    table_name = os.environ.get("ATHENA_TABLE_REGISTRY_TABLE")
    table = dynamodb.Table(table_name)
    response = table.scan()
    return {item["log_type"]: item for item in response.get("Items", [])}

def build_llm1_prompt(user_input):
    registry = get_table_registry()
    ct_table = registry["cloudtrail"]["table_name"]
    ct_location = registry["cloudtrail"]["s3_path"]
    gd_table = registry["guardduty"]["table_name"]
    gd_location = registry["guardduty"]["s3_path"]

    return f'''
You are a SQL generation expert for AWS Athena (Presto SQL).
Generate ONLY SQL code that is valid in Athena with no explanation.

Task:
Convert the following natural language question into an SQL query.

Context information:
- Database Table DDL:
    - cloudtrail:
        CREATE EXTERNAL TABLE `{ct_table}`(
            `eventversion` string COMMENT 'from deserializer', 
            `useridentity` struct<type:string,principalid:string,arn:string,accountid:string,invokedby:string,accesskeyid:string,username:string,sessioncontext:struct<attributes:struct<mfaauthenticated:string,creationdate:string>,sessionissuer:struct<type:string,principalid:string,arn:string,accountid:string,username:string>,ec2roledelivery:string,webidfederationdata:struct<federatedprovider:string,attributes:map<string,string>>>> COMMENT 'from deserializer', 
            `eventtime` string COMMENT 'from deserializer', 
            `eventsource` string COMMENT 'from deserializer', 
            `eventname` string COMMENT 'from deserializer', 
            `awsregion` string COMMENT 'from deserializer', 
            `sourceipaddress` string COMMENT 'from deserializer', 
            `useragent` string COMMENT 'from deserializer', 
            `errorcode` string COMMENT 'from deserializer', 
            `errormessage` string COMMENT 'from deserializer', 
            `requestparameters` string COMMENT 'from deserializer', 
            `responseelements` string COMMENT 'from deserializer', 
            `additionaleventdata` string COMMENT 'from deserializer', 
            `requestid` string COMMENT 'from deserializer', 
            `eventid` string COMMENT 'from deserializer', 
            `resources` array<struct<arn:string,accountid:string,type:string>> COMMENT 'from deserializer', 
            `eventtype` string COMMENT 'from deserializer', 
            `apiversion` string COMMENT 'from deserializer', 
            `readonly` string COMMENT 'from deserializer', 
            `recipientaccountid` string COMMENT 'from deserializer', 
            `serviceeventdetails` string COMMENT 'from deserializer', 
            `sharedeventid` string COMMENT 'from deserializer', 
            `vpcendpointid` string COMMENT 'from deserializer', 
            `tlsdetails` struct<tlsversion:string,ciphersuite:string,clientprovidedhostheader:string> COMMENT 'from deserializer')
            PARTITIONED BY ( 
            `partition_date` string)
            ROW FORMAT SERDE 
            'org.apache.hive.hcatalog.data.JsonSerDe' 
            STORED AS INPUTFORMAT 
            'com.amazon.emr.cloudtrail.CloudTrailInputFormat' 
            OUTPUTFORMAT 
            'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
            LOCATION
            '{ct_location}'
            TBLPROPERTIES (
            'projection.enabled'='true', 
            'projection.partition_date.format'='yyyy/MM/dd', 
            'projection.partition_date.interval'='1', 
            'projection.partition_date.interval.unit'='DAYS', 
            'projection.partition_date.range'='2025/01/01,NOW', 
            'projection.partition_date.type'='date', 
            'storage.location.template'='s3://wga-cloudtrail-2/AWSLogs/339712974607/CloudTrail/us-east-1/$partition_date', 
            'transient_lastDdlTime'='1744721089')
    
    - guardduty:
        CREATE EXTERNAL TABLE `{gd_table}`(
            `version` string COMMENT 'from deserializer', 
            `id` string COMMENT 'from deserializer', 
            `detail_type` string COMMENT 'from deserializer', 
            `source` string COMMENT 'from deserializer', 
            `account` string COMMENT 'from deserializer', 
            `time` string COMMENT 'from deserializer', 
            `region` string COMMENT 'from deserializer', 
            `resources` array<string> COMMENT 'from deserializer', 
            `detail` string COMMENT 'from deserializer')
            PARTITIONED BY ( 
            `partition_date` string)
            ROW FORMAT SERDE 
            'org.openx.data.jsonserde.JsonSerDe' 
            WITH SERDEPROPERTIES ( 
            'ignore.malformed.json'='true') 
            STORED AS INPUTFORMAT 
            'org.apache.hadoop.mapred.TextInputFormat' 
            OUTPUTFORMAT 
            'org.apache.hadoop.hive.ql.io.IgnoreKeyTextOutputFormat'
            LOCATION
            '{gd_location}'
            TBLPROPERTIES (
            'projection.enabled'='true', 
            'projection.partition_date.format'='yyyy/MM/dd/HH', 
            'projection.partition_date.interval'='1', 
            'projection.partition_date.interval.unit'='HOURS', 
            'projection.partition_date.range'='2025/01/01/00,NOW', 
            'projection.partition_date.type'='date', 
            'storage.location.template'='s3://wga-guardduty-logs/guardduty-logs/$partition_date', 
            'transient_lastDdlTime'='1744721093')

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
    return requests.post(f'{CONFIG['api']['endpoint']}/create-table', json=payload) # create-table API URL을 여기에 입력하세요

def call_create_table_guardduty():
    CONFIG = get_config()
    payload = {
        "log_type": "guardduty",
        "s3_path": "s3://wga-guardduty-logs/guardduty-logs/",
        "table_name": "guardduty_logs"
    }
    return requests.post(f'{CONFIG['api']['endpoint']}/create-table', json=payload) # create-table API URL을 여기에 입력하세요


def call_execute_query(sql_query):
    CONFIG = get_config()
    wrapper_payload = {
        "query": sql_query
    }
    res =  requests.post(f'{CONFIG['api']['endpoint']}/execute-query', json=wrapper_payload) # Athena 쿼리 실행 API URL을 여기에 입력하세요
    return res.json()

def send_slack_dm(user_id, message):
    CONFIG = get_config()
    client = WebClient(token=CONFIG['slackbot']['token']) # 여기에 Slack Bot Token

    
    response = client.chat_postMessage(
        channel=user_id,  # 여기서 user_id 그대로 DM 채널로 사용 가능
        text=message
    )
    if not response["ok"]:
        print("❌ Slack 메시지 실패 사유:", response["error"])
    return response

def handle_llm1_request(body, CONFIG, origin):
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

    send_slack_dm(slack_user_id, f"🧠 분석 결과:\n{text_answer}")

    return cors_response(200, {
        "status": "쿼리 생성 완료",
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
