import os
import json
import boto3
from botocore.exceptions import ClientError

# 환경 변수에서 설정 불러오기
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
ENV = os.environ.get('ENV', 'dev')

# AWS SSM에서 비밀 설정 가져오기
def get_ssm_parameter(param_name, with_decryption=True):
    """
    AWS SSM Parameter Store에서 파라미터 값을 가져옵니다.
    """
    ssm = boto3.client('ssm', region_name=AWS_REGION)
    try:
        response = ssm.get_parameter(Name=param_name, WithDecryption=with_decryption)
        return response['Parameter']['Value']
    except ClientError as e:
        print(f"Error getting parameter {param_name}: {e}")
        return None

# 설정 값을 한 번에 불러오는 함수
def load_config():
    """
    애플리케이션에 필요한 모든 설정 값을 로드합니다.
    """
    config = {
        'aws_region': AWS_REGION,
        'env': ENV,
        'amplify': {
            'app_id': '',
            'default_domain': '',
            'default_domain_with_env': ''
        },
        'api': {
            'endpoint': '',
            'gateway_id': '',
            'root_resource_id': ''
        },
        's3': {
            'athena_output_bucket': '',
            'deployment_bucket': '',
            'guardduty_export_bucket': ''
        },
        'frontend': {
            'redirect_domain': ''
        },
        'cognito': {
            'user_pool_id': '',
            'client_id': '',
            'domain': '',
            'identity_pool_id': ''
        },
        'slackbot': {
            'token': ''
        },
    }

    try:
        # SSM 파라미터 경로
        ssm_path = f'/wga/{ENV}/'

        # SSM에서 모든 파라미터 로드
        ssm = boto3.client('ssm', region_name=AWS_REGION)
        response = ssm.get_parameters_by_path(
            Path=ssm_path,
            WithDecryption=True,
            Recursive=True
        )

        # 설정에 추가
        mapping = {
            'AmplifyAppId': ('amplify', 'app_id'),
            'AmplifyDefaultDomain': ('amplify', 'default_domain'),
            'AmplifyDefaultDomainWithEnv': ('amplify', 'default_domain_with_env'),
            'ApiEndpoint': ('api', 'endpoint'),
            'ApiGatewayId': ('api', 'gateway_id'),
            'ApiGatewayRootResourceId': ('api', 'root_resource_id'),
            'AthenaOutputBucketName': ('s3', 'athena_output_bucket'),
            'DeploymentBucketName': ('s3', 'deployment_bucket'),
            'FrontendRedirectDomain': ('frontend', 'redirect_domain'),
            'GuardDutyExportBucketName': ('s3', 'guardduty_export_bucket'),
            'IdentityPoolId': ('cognito', 'identity_pool_id'),
            'OutputBucketName': ('s3', 'output_bucket'),
            'SlackbotToken': ('slackbot', 'token'),
            'UserPoolClientId': ('cognito', 'client_id'),
            'UserPoolDomain': ('cognito', 'domain'),
            'UserPoolId': ('cognito', 'user_pool_id')
        }

        for param in response.get('Parameters', []):
            name = param['Name'].replace(ssm_path, '')
            value = param['Value']

            # 파라미터 이름에 따라 적절한 위치에 추가
            if name in mapping:
                section, key = mapping[name]
                config[section][key] = value

    except Exception as e:
        print(f"Error loading SSM parameters: {e}")

    
    return config

# 구성 로드
CONFIG = load_config()