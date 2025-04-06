# lambda_functions/common/config.py
import os
import json
import boto3
from botocore.exceptions import ClientError

# 환경 변수에서 설정 불러오기
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
ENV = os.environ.get('ENV', 'dev')

# DynamoDB 테이블
SESSIONS_TABLE = os.environ.get('SESSIONS_TABLE', f'Sessions-{ENV}')
USERS_TABLE = os.environ.get('USERS_TABLE', f'Users-{ENV}')
ANALYSIS_RESULTS_TABLE = os.environ.get('ANALYSIS_RESULTS_TABLE', f'AnalysisResults-{ENV}')
USER_BEHAVIOR_PROFILES_TABLE = os.environ.get('USER_BEHAVIOR_PROFILES_TABLE', f'UserBehaviorProfiles-{ENV}')
ROLE_TEMPLATES_TABLE = os.environ.get('ROLE_TEMPLATES_TABLE', f'RoleTemplates-{ENV}')
ROLE_HISTORY_TABLE = os.environ.get('ROLE_HISTORY_TABLE', f'RoleHistory-{ENV}')
ANOMALY_EVENTS_TABLE = os.environ.get('ANOMALY_EVENTS_TABLE', f'AnomalyEvents-{ENV}')
ACCESS_DECISIONS_TABLE = os.environ.get('ACCESS_DECISIONS_TABLE', f'AccessDecisions-{ENV}')

# S3 버킷
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'wga-outputbucket')

# AWS Cognito 설정
USER_POOL_ID = os.environ.get('USER_POOL_ID', '')
COGNITO_CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID', '')
COGNITO_DOMAIN = os.environ.get('COGNITO_DOMAIN', '')
COGNITO_IDENTITY_POOL_ID = os.environ.get('COGNITO_IDENTITY_POOL_ID', '')

# SNS 주제
SNS_ALERT_TOPIC = os.environ.get('SNS_ALERT_TOPIC', f'wga-security-alerts-{ENV}')

# 제로 트러스트 설정
ZERO_TRUST_CONFIG = {
    'session_duration': int(os.environ.get('SESSION_DURATION', '3600')),
    'mfa_required_threshold': int(os.environ.get('MFA_REQUIRED_THRESHOLD', '50')),
    'deny_threshold': int(os.environ.get('DENY_THRESHOLD', '70')),
    'continuous_auth_interval': int(os.environ.get('CONTINUOUS_AUTH_INTERVAL', '900'))
}

# CORS 설정
CORS_SETTINGS = {
    'dev': {
        'allowed_origins': ['http://localhost:5173'],
        'allowed_methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        'allowed_headers': ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key', 'X-Amz-Security-Token'],
        'allow_credentials': True
    },
    'test': {
        'allowed_origins': ['https://test-app.example.com'],
        'allowed_methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        'allowed_headers': ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key', 'X-Amz-Security-Token'],
        'allow_credentials': True
    },
    'prod': {
        'allowed_origins': ['https://app.example.com'],
        'allowed_methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        'allowed_headers': ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key', 'X-Amz-Security-Token'],
        'allow_credentials': True
    }
}

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
        'tables': {
            'sessions': SESSIONS_TABLE,
            'users': USERS_TABLE,
            'analysis_results': ANALYSIS_RESULTS_TABLE,
            'user_behavior_profiles': USER_BEHAVIOR_PROFILES_TABLE,
            'role_templates': ROLE_TEMPLATES_TABLE,
            'role_history': ROLE_HISTORY_TABLE,
            'anomaly_events': ANOMALY_EVENTS_TABLE,
            'access_decisions': ACCESS_DECISIONS_TABLE
        },
        's3': {
            'output_bucket': OUTPUT_BUCKET
        },
        'cognito': {
            'user_pool_id': USER_POOL_ID,
            'client_id': COGNITO_CLIENT_ID,
            'domain': COGNITO_DOMAIN,
            'identity_pool_id': COGNITO_IDENTITY_POOL_ID
        },
        'sns': {
            'anomaly_alert_topic': SNS_ALERT_TOPIC
        },
        'zero_trust': ZERO_TRUST_CONFIG,
        # 개발자 모드 설정 - 개발 환경에서는 기본적으로 활성화
        'developer_mode': ENV == 'dev',
        # CORS 설정 추가
        'cors': CORS_SETTINGS.get(ENV, CORS_SETTINGS['dev'])
    }
    
    # 환경 변수로 개발자 모드 설정을 재정의 가능하도록
    developer_mode_env = os.environ.get('DEVELOPER_MODE', '')
    if developer_mode_env.lower() in ('true', 'yes', '1'):
        config['developer_mode'] = True
    elif developer_mode_env.lower() in ('false', 'no', '0'):
        config['developer_mode'] = False
    
    # 개발 환경이 아니라면 SSM에서 추가 비밀 설정 로드
    if ENV != 'dev':
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
            for param in response.get('Parameters', []):
                name = param['Name'].replace(ssm_path, '')
                value = param['Value']
                
                # 파라미터 이름에 따라 적절한 위치에 추가
                if name.startswith('cognito_'):
                    config['cognito'][name.replace('cognito_', '')] = value
            
        except Exception as e:
            print(f"Error loading SSM parameters: {e}")
    
    return config

# 구성 로드
CONFIG = load_config()