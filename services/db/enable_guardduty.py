import boto3
import os

guardduty = boto3.client('guardduty')
region = os.environ.get("AWS_REGION", "us-east-1")

def lambda_handler(event, context):
    try:
        response = guardduty.create_detector(Enable=True)
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