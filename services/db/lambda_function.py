import boto3
import json
import os
import time
import textwrap
from urllib.parse import urlparse

athena = boto3.client("athena")
s3 = boto3.client("s3")

ATHENA_DB = os.environ.get("ATHENA_DB")
S3_OUTPUT = os.environ.get("S3_QUERY_OUTPUT")

def wait_for_query(query_id):
    while True:
        response = athena.get_query_execution(QueryExecutionId=query_id)
        state = response["QueryExecution"]["Status"]["State"]
        if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            break
        time.sleep(2)
    if state != "SUCCEEDED":
        reason = response["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
        raise Exception(f"Athena query failed with state: {state}, reason: {reason}")

def get_create_table_query(log_type, s3_path, table_name):
    if log_type == "cloudtrail":
        return textwrap.dedent(f"""CREATE EXTERNAL TABLE IF NOT EXISTS guardduty_findings (
  schemaVersion string,
  accountId string,
  region string,
  id string,
  arn string,
  type string,
  resource struct<
    resourceType: string,
    accessKeyDetails: struct<
      accessKeyId: string,
      principalId: string,
      userType: string,
      userName: string
    >
  >,
  service struct<
    action: struct<
      actionType: string,
      awsApiCallAction: struct<
        api: string,
        serviceName: string
      >
    >,
    additionalInfo: map<string, string>,
    eventFirstSeen: string,
    eventLastSeen: string
  >,
  severity double,
  createdAt string,
  updatedAt string,
  title string,
  description string
)
PARTITIONED BY (
  year string,
  month string,
  day string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
  'ignore.malformed.json' = 'true'
)
STORED AS TEXTFILE
LOCATION 's3://wga-guardduty-logs/guardduty-logs/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.year.type'='integer',
  'projection.year.range'='2024,2026',
  'projection.month.type'='integer',
  'projection.month.range'='1,12',
  'projection.day.type'='integer',
  'projection.day.range'='1,31',
  'storage.location.template'='s3://wga-guardduty-logs/guardduty-logs/${year}/${month}/${day}/'
);
""")

    elif log_type == "guardduty":
        return textwrap.dedent(f"""CREATE EXTERNAL TABLE IF NOT EXISTS {ATHENA_DB}.{table_name} (
    schemaVersion string,
    accountId string,
    region string,
    id string,
    arn string,
    type string,
    resource struct<
        resourceType: string,
        accessKeyDetails: struct<
            accessKeyId: string,
            principalId: string,
            userType: string,
            userName: string
        >
    >,
    service struct<
        action: struct<
            actionType: string,
            awsApiCallAction: struct<
                api: string,
                serviceName: string
            >
        >,
        additionalInfo: map<string, string>,
        eventFirstSeen: string,
        eventLastSeen: string
    >,
    severity double,
    createdAt string,
    updatedAt string,
    title string,
    description string
)
PARTITIONED BY (
    year string,
    month string,
    day string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
    'ignore.malformed.json' = 'true'
)
STORED AS TEXTFILE
LOCATION '{s3_path}'
TBLPROPERTIES (
    'projection.enabled'='true',
    'projection.year.type'='integer',
    'projection.year.range'='2024,2026',
    'projection.month.type'='integer',
    'projection.month.range'='1,12',
    'projection.day.type'='integer',
    'projection.day.range'='1,31',
    'storage.location.template'='{s3_path}${{year}}/${{month}}/${{day}}/'
);""")
    else:
        raise ValueError(f"Unsupported log_type: {log_type}")

def lambda_handler(event, context):
    try:
        # ✅ 1차 디코딩: API Gateway로 들어온 경우
        if isinstance(event.get("body"), str):
            outer_body = json.loads(event["body"])
        else:
            outer_body = event.get("body", {})

        # ✅ 2차 디코딩: Lambda 테스트 이벤트로 실행한 경우
        path = outer_body.get("path", event.get("path", ""))
        http_method = outer_body.get("httpMethod", event.get("httpMethod", ""))
        inner_body = json.loads(outer_body.get("body", "{}"))

        # =====================
        # /execute-query
        # =====================
        if path == "/execute-query" and http_method == "POST":
            query = inner_body.get("query")
            if not query:
                return {"statusCode": 400, "body": json.dumps({"error": "Missing 'query' in request."})}

            create_db_query = f"CREATE DATABASE IF NOT EXISTS {ATHENA_DB}"
            db_exec_id = athena.start_query_execution(
                QueryString=create_db_query,
                ResultConfiguration={"OutputLocation": S3_OUTPUT}
            )["QueryExecutionId"]
            wait_for_query(db_exec_id)

            exec_id = athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": ATHENA_DB},
                ResultConfiguration={"OutputLocation": S3_OUTPUT}
            )["QueryExecutionId"]
            wait_for_query(exec_id)

            results = athena.get_query_results(QueryExecutionId=exec_id)
            columns = [col["VarCharValue"] for col in results["ResultSet"]["Rows"][0]["Data"]]
            records = []
            for row in results["ResultSet"]["Rows"][1:]:
                record = {}
                for i, col in enumerate(row["Data"]):
                    record[columns[i]] = col.get("VarCharValue", "")
                records.append(record)

            return {"statusCode": 200, "body": json.dumps(records, ensure_ascii=False)}

        # =====================
        # /create-table
        # =====================
        elif path == "/create-table" and http_method == "POST":
            log_type = inner_body.get("log_type")
            s3_path = inner_body.get("s3_path")
            table_name = inner_body.get("table_name", f"{log_type}_logs")

            if not log_type or not s3_path:
                return {"statusCode": 400, "body": json.dumps({"error": "Missing 'log_type' or 's3_path'"})}

            create_db_query = f"CREATE DATABASE IF NOT EXISTS {ATHENA_DB}"
            db_exec_id = athena.start_query_execution(
                QueryString=create_db_query,
                ResultConfiguration={"OutputLocation": S3_OUTPUT}
            )["QueryExecutionId"]
            wait_for_query(db_exec_id)

            query = get_create_table_query(log_type, s3_path, table_name)
            exec_id = athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": ATHENA_DB},
                ResultConfiguration={"OutputLocation": S3_OUTPUT}
            )["QueryExecutionId"]
            wait_for_query(exec_id)

            return {
                "statusCode": 200,
                "body": f"✅ {log_type} projection 테이블 생성 완료: {ATHENA_DB}.{table_name}"
            }

        # =====================
        # Not Found
        # =====================
        else:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"Route {http_method} {path} not found."})
            }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
