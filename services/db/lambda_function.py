import boto3
import json
from common.db import wait_for_query, get_create_table_query, execute_query, create_table

def lambda_handler(event, context):
    try:
        path = event.get("path", "")
        http_method = event.get("httpMethod", "")
        body = json.loads(event.get("body", "{}"))

        if path == "/execute-query" and http_method == "POST":
            query = body.get("query")
            if not query:
                return {"statusCode": 400, "body": json.dumps({"error": "Missing 'query' in request."})}

            records = execute_query(query)

            return {"statusCode": 200, "body": json.dumps(records, ensure_ascii=False)}

        elif path == "/create-table" and http_method == "POST":
            log_type = body.get("log_type")
            s3_path = body.get("s3_path")
            table_name = body.get("table_name", f"{log_type}_logs")

            if not log_type or not s3_path:
                return {"statusCode": 400, "body": json.dumps({"error": "Missing 'log_type' or 's3_path'"})}

            result = create_table(log_type, s3_path, table_name)
            return result

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
