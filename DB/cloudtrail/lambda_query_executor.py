import boto3
import json
import re
import time
import os
from datetime import datetime

athena = boto3.client('athena')
s3 = boto3.client('s3')

def wait_for_query(query_id):
    while True:
        response = athena.get_query_execution(QueryExecutionId=query_id)
        state = response["QueryExecution"]["Status"]["State"]
        if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            break
        time.sleep(2)
    if state != "SUCCEEDED":
        raise Exception(f"Athena query failed with state: {state}")

def create_table(s3_path):
    database = "logdb"
    table_name = "cloudtrail_logs"
    account_id_search = re.search(r"AWSLogs\/(\d+)\/CloudTrail", s3_path)
    region_search = re.search(r"CloudTrail\/([^\/]+)\/", s3_path)

    if not account_id_search or not region_search:
        raise ValueError("Invalid S3 path format for CloudTrail logs.")

    account_id = account_id_search.group(1)
    region = region_search.group(1)

    query = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {database}.{table_name} (
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
    );
    """
    execution = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": "s3://wga-gluequery-1"}
    )
    wait_for_query(execution["QueryExecutionId"])

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

        if s3_path:
            create_table(s3_path)

        exec_id = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": "logdb"},
            ResultConfiguration={"OutputLocation": "s3://wga-gluequery-1"}
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
