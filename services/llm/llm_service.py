# 프롬프트 slack to llm1
import json
import urllib.parse
from slack_sdk import WebClient
from common.config import CONFIG
import requests

def build_llm1_prompt(user_input):
    return f'''
You are a SQL generation expert for AWS Athena (Presto SQL).
Generate ONLY SQL code that is valid in Athena with no explanation.

Task:
Convert the following natural language question into an SQL query.

Context information:
- Database Table DDL:
    - cloudtrail:
        CREATE EXTERNAL TABLE `cloudtrail_logs`(
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
            's3://wga-cloudtrail-2/AWSLogs/339712974607/CloudTrail/us-east-1'
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
        CREATE EXTERNAL TABLE `guardduty_logs`(
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
            's3://wga-guardduty-logs/guardduty-logs'
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
    payload = {
        "log_type": "cloudtrail",
        "s3_path": "s3://wga-cloudtrail-2/AWSLogs/339712974607/CloudTrail/us-east-1/",
        "table_name": "cloudtrail_logs"
    }
    return requests.post(f'{CONFIG['api']['endpoint']}/create-table', json=payload) # create-table API URL을 여기에 입력하세요

def call_create_table_guardduty():
    payload = {
        "log_type": "guardduty",
        "s3_path": "s3://wga-guardduty-logs/guardduty-logs/",
        "table_name": "guardduty_logs"
    }
    return requests.post(f'{CONFIG['api']['endpoint']}/create-table', json=payload) # create-table API URL을 여기에 입력하세요


def call_execute_query(sql_query):
    wrapper_payload = {
        "query": sql_query
    }
    res =  requests.post(f'{CONFIG['api']['endpoint']}/execute-query', json=wrapper_payload) # Athena 쿼리 실행 API URL을 여기에 입력하세요
    return res.json()

def send_slack_dm(user_id, message):
    client = WebClient(token=CONFIG['slackbot']['token']) # 여기에 Slack Bot Token

    
    response = client.chat_postMessage(
        channel=user_id,  # 여기서 user_id 그대로 DM 채널로 사용 가능
        text=message
    )
    if not response["ok"]:
        print("❌ Slack 메시지 실패 사유:", response["error"])
    return response
