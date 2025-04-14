import boto3
import json
import os
import time

athena = boto3.client('athena')

ATHENA_DB = os.environ.get("ATHENA_DATABASE", "logdb")
S3_OUTPUT = os.environ.get("S3_QUERY_OUTPUT", "s3://wga-gluequery-1")

def wait_for_query(query_id):
    while True:
        response = athena.get_query_execution(QueryExecutionId=query_id)
        state = response["QueryExecution"]["Status"]["State"]
        if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            break
        time.sleep(2)
    if state != "SUCCEEDED":
        raise Exception(f"Athena query failed: {state}")

def lambda_handler(event, context):
    try:
        body = event.get("body")
        if isinstance(body, str):
            body = json.loads(body)
        query = body.get("query")
        if not query:
            return {"statusCode": 400, "body": "Missing 'query'"}

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
