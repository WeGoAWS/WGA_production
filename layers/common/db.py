# layers/common/db.py
import boto3
import os
import time
import textwrap
from urllib.parse import urlparse

athena = boto3.client("athena")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("AthenaTableRegistry")
ATHENA_DB = os.environ.get("ATHENA_DB", "")
S3_OUTPUT = os.environ.get("S3_QUERY_OUTPUT", "")

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
        PARTITIONED BY (`partition_date` string)
        ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerDe'
        STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
        OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
        LOCATION '{s3_path}'
        TBLPROPERTIES (
          'projection.enabled'='true',
          'projection.partition_date.format'='yyyy/MM/dd',
          'projection.partition_date.interval'='1',
          'projection.partition_date.interval.unit'='DAYS',
          'projection.partition_date.range'='2025/01/01,NOW',
          'projection.partition_date.type'='date',
          'storage.location.template'='{s3_path}${{partition_date}}'
        );""")

    elif log_type == "guardduty":
        return textwrap.dedent(f"""CREATE EXTERNAL TABLE IF NOT EXISTS {ATHENA_DB}.{table_name} (
  `version` string COMMENT 'from deserializer', 
  `id` string COMMENT 'from deserializer', 
  `detail_type` string COMMENT 'from deserializer', 
  `source` string COMMENT 'from deserializer', 
  `account` string COMMENT 'from deserializer', 
  `time` string COMMENT 'from deserializer', 
  `region` string COMMENT 'from deserializer', 
  `resources` array<string> COMMENT 'from deserializer', 
  `detail` string COMMENT 'from deserializer')
PARTITIONED BY (`partition_date` string)
ROW FORMAT SERDE 
  'org.openx.data.jsonserde.JsonSerDe' 
WITH SERDEPROPERTIES ( 
  'ignore.malformed.json'='true') 
STORED AS INPUTFORMAT 
  'org.apache.hadoop.mapred.TextInputFormat' 
OUTPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.IgnoreKeyTextOutputFormat'
LOCATION '{s3_path}'
TBLPROPERTIES (
  'projection.partition_date.type'='date',
  'projection.partition_date.format'='yyyy/MM/dd/HH',
  'projection.partition_date.range'='2025/01/01/00,NOW',
  'projection.partition_date.interval'='1',
  'projection.partition_date.interval.unit'='HOURS',
  'projection.enabled'='true',
  'storage.location.template'='{s3_path}${{partition_date}}'
);""")

    else:
        raise ValueError(f"Unsupported log_type: {log_type}")

def execute_query(query):
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

    return records

def create_table(log_type, s3_path, table_name):
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

    table.put_item(
        Item={
            "log_type": log_type,
            "table_name": table_name,
            "s3_path": s3_path,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    )

    return {
        "statusCode": 200,
        "body": f"✅ {log_type} 테이블 생성 완료: {ATHENA_DB}.{table_name}"
    }