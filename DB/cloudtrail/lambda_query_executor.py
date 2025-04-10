import boto3
import json
import time
import os
from datetime import datetime

athena = boto3.client('athena')
s3 = boto3.client('s3')

ATHENA_DB = os.environ.get("ATHENA_DB", "logdb")
S3_OUTPUT = os.environ.get("S3_QUERY_OUTPUT", "s3://wga-gluequery-1") 

def wait_for_query(query_id):
    while True:
        response = athena.get_query_execution(QueryExecutionId=query_id)
        state = response["QueryExecution"]["Status"]["State"]
        if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            break
        time.sleep(2)
    if state != "SUCCEEDED":
        raise Exception(f"Athena query failed with state: {state}")

def lambda_handler(event, context):
    try:
        # event['query'] or body의 쿼리문 추출
        body = event.get("body")
        if isinstance(body, str):
            body = json.loads(body)
        query = body.get("query")
        s3_path = body.get("s3_path")  # optional

        if not query:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing 'query' in request."})}

        # 데이터베이스가 없으면 생성
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

        return {
            "statusCode": 200,
            "body": json.dumps(records, ensure_ascii=False)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
