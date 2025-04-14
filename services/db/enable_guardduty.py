import boto3
import os

guardduty = boto3.client('guardduty')
region = os.environ.get("AWS_REGION", "us-east-1")

def lambda_handler(event, context):
    try:
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()["Account"]
        s3_bucket_name = os.environ.get("GUARDDUTY_S3_BUCKET", f"wga-guardduty-logs-{account_id}-{region}")
        s3 = boto3.client('s3')
        try:
            s3.head_bucket(Bucket=s3_bucket_name)
        except s3.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                s3.create_bucket(Bucket=s3_bucket_name)
        
        response = guardduty.create_detector(
            Enable=True,
            FindingPublishingFrequency="FIFTEEN_MINUTES",
            DataSources={
                'S3Logs': {
                    'Enable': True
                }
            }
        )
        detector_id = response['DetectorId']
        return {
            'statusCode': 200,
            'body': f"GuardDuty Detector created: {detector_id}"
        }
    except guardduty.exceptions.BadRequestException as e:
        return {
            'statusCode': 400,
            'body': f"GuardDuty already enabled or bad request: {str(e)}"
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }