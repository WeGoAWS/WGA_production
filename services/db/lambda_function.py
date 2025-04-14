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
        raise Exception(f"Athena query failed with state: {state}")

def get_create_table_query(log_type, s3_path, table_name):
    if log_type == "cloudtrail":
        return textwrap.dedent(f"""CREATE EXTERNAL TABLE IF NOT EXISTS {ATHENA_DB}.{table_name} (
          `eventversion` string,
          `useridentity` struct<type:string,principalid:string,arn:string,accountid:string,invokedby:string,accesskeyid:string,username:string,sessioncontext:struct<attributes:struct<mfaauthenticated:string,creationdate:string>,sessionissuer:struct<type:string,principalid:string,arn:string,accountid:string,username:string>,ec2roledelivery:string,webidfederationdata:struct<federatedprovider:string,attributes:map<string,string>>>>,
          `eventtime` string,
          `eventsource` string,
          `eventname` string,
          `awsregion` string,
          `sourceipaddress` string,
          `useragent` string,
          `errorcode` string,
          `errormessage` string,
          `requestparameters` string,
          `responseelements` string,
          `additionaleventdata` string,
          `requestid` string,
          `eventid` string,
          `resources` array<struct<arn:string,accountid:string,type:string>>,
          `eventtype` string,
          `apiversion` string,
          `readonly` string,
          `recipientaccountid` string,
          `serviceeventdetails` string,
          `sharedeventid` string,
          `vpcendpointid` string,
          `tlsdetails` struct<tlsversion:string,ciphersuite:string,clientprovidedhostheader:string>)
        PARTITIONED BY (`timestamp` string)
        ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerDe'
        STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
        OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
        LOCATION '{s3_path}'
        TBLPROPERTIES (
          'projection.enabled'='true',
          'projection.timestamp.format'='yyyy/MM/dd',
          'projection.timestamp.interval'='1',
          'projection.timestamp.interval.unit'='DAYS',
          'projection.timestamp.range'='2025/01/01,NOW',
          'projection.timestamp.type'='date',
          'storage.location.template'='{s3_path}${{timestamp}}'
        );""")

    elif log_type == "guardduty":
        return textwrap.dedent(f"""CREATE EXTERNAL TABLE IF NOT EXISTS {ATHENA_DB}.{table_name} (
          `schemaVersion` string,
          `accountId` string,
          `region` string,
          `id` string,
          `arn` string,
          `type` string,
          `resource` string,
          `service` string,
          `severity` double,
          `createdAt` string,
          `updatedAt` string,
          `title` string,
          `description` string
        )
        ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
        WITH SERDEPROPERTIES (
          'ignore.malformed.json' = 'true'
        )
        LOCATION '{s3_path}';""")

    else:
        raise ValueError(f"Unsupported log_type: {log_type}")

def lambda_handler(event, context):
    try:
        path = event.get("path", "")
        http_method = event.get("httpMethod", "")
        body = json.loads(event.get("body", "{}"))

        # /execute-query
        if path == "/execute-query" and http_method == "POST":
            query = body.get("query")
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

        # /create-table
        elif path == "/create-table" and http_method == "POST":
            log_type = body.get("log_type")
            s3_path = body.get("s3_path")
            table_name = body.get("table_name", f"{log_type}_logs")

            if not log_type or not s3_path:
                return {"statusCode": 400, "body": json.dumps({"error": "Missing 'log_type' or 's3_path'"})}

            parsed = urlparse(S3_OUTPUT)
            bucket_name = parsed.netloc
            try:
                s3.head_bucket(Bucket=bucket_name)
            except s3.exceptions.ClientError as e:
                if e.response['Error']['Code'] == '404':
                    s3.create_bucket(Bucket=bucket_name)

            create_db_query = f"CREATE DATABASE IF NOT EXISTS {ATHENA_DB}"
            db_exec_id = athena.start_query_execution(
                QueryString=create_db_query,
                ResultConfiguration={"OutputLocation": S3_OUTPUT}
            )["QueryExecutionId"]
            wait_for_query(db_exec_id)

            query = get_create_table_query(log_type, s3_path, table_name)
            exec_id = athena.start_query_execution(
                QueryString=query,
                ResultConfiguration={"OutputLocation": S3_OUTPUT}
            )["QueryExecutionId"]
            wait_for_query(exec_id)

            return {
                "statusCode": 200,
                "body": f"✅ {log_type} 테이블 생성 완료: {ATHENA_DB}.{table_name}"
            }

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