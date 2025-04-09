import boto3
import re
import os
import time
import json

athena = boto3.client("athena")

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

def get_create_table_query(log_type, s3_path, table_name):
    if log_type == "cloudtrail":
        return f"""
        CREATE EXTERNAL TABLE IF NOT EXISTS {ATHENA_DB}.{table_name} (
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
    
    elif log_type == "guardduty":
        return f"""
        CREATE EXTERNAL TABLE IF NOT EXISTS {ATHENA_DB}.{table_name} (
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
        LOCATION '{s3_path}';
        """
    
    else:
        raise ValueError(f"Unsupported log_type: {log_type}")

def lambda_handler(event, context):
    try:
        body = event.get("body")
        if isinstance(body, str):
            body = json.loads(body)
        
        log_type = body.get("log_type")
        s3_path = body.get("s3_path")
        table_name = body.get("table_name", f"{log_type}_logs")

        if not log_type or not s3_path:
            return {"statusCode": 400, "body": "Missing 'log_type' or 's3_path'"}

        query = get_create_table_query(log_type, s3_path, table_name)

        exec_id = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": ATHENA_DB},
            ResultConfiguration={"OutputLocation": S3_OUTPUT}
        )["QueryExecutionId"]

        wait_for_query(exec_id)

        return {
            "statusCode": 200,
            "body": f"✅ {log_type} 테이블 생성 완료: {ATHENA_DB}.{table_name}"
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
