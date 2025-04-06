#!/bin/bash
# WGA - 배포 스크립트

# 오류 발생 시 스크립트 중단
set -e

# 환경 변수 설정
ENV=${1:-dev}  # 기본값: dev
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
REGION=$(aws configure get region)

echo "배포 환경: $ENV"
echo "AWS 계정 ID: $ACCOUNT_ID"
echo "AWS 리전: $REGION"

# 배포 버킷 이름
CLOUDFORMATION_BUCKET="wga-cloudformation-$ACCOUNT_ID"
DEPLOYMENT_BUCKET="wga-deployment-$ENV"
OUTPUT_BUCKET_NAME="wga-outputbucket-$ENV"

# 버킷 존재 여부 확인 및 생성
echo "CloudFormation 템플릿을 저장할 $CLOUDFORMATION_BUCKET 버킷 확인 중..."
if ! aws s3 ls "s3://$CLOUDFORMATION_BUCKET" 2>&1 > /dev/null; then
    echo "$CLOUDFORMATION_BUCKET 버킷이 존재하지 않습니다. 생성합니다..."
    aws s3 mb "s3://$CLOUDFORMATION_BUCKET" --region $REGION
    aws s3api put-bucket-versioning --bucket "$CLOUDFORMATION_BUCKET" --versioning-configuration Status=Enabled
    echo "$CLOUDFORMATION_BUCKET 버킷 생성 완료"
else
    echo "$CLOUDFORMATION_BUCKET 버킷이 이미 존재합니다"
fi

echo "====== CloudFormation 템플릿 업로드 ======"
# 배포 버킷이 존재하지 않을 수 있으므로 base 스택을 먼저 배포
echo "CloudFormation 템플릿 업로드 중..."
aws s3 cp cloudformation/base.yaml "s3://$CLOUDFORMATION_BUCKET/base.yaml"
aws s3 cp cloudformation/auth.yaml "s3://$CLOUDFORMATION_BUCKET/auth.yaml"
aws s3 cp cloudformation/security-analytics.yaml "s3://$CLOUDFORMATION_BUCKET/security-analytics.yaml" 2>/dev/null || echo "security-analytics.yaml 파일이 없습니다. 스킵합니다."
aws s3 cp cloudformation/zero-trust.yaml "s3://$CLOUDFORMATION_BUCKET/zero-trust.yaml" 2>/dev/null || echo "zero-trust.yaml 파일이 없습니다. 스킵합니다."
aws s3 cp cloudformation/main.yaml "s3://$CLOUDFORMATION_BUCKET/main.yaml"

echo "CloudFormation 템플릿 업로드 완료"

echo "====== 기본 인프라 스택 배포 ======"

# 기본 스택 배포 전 S3 버킷 존재 여부 확인
if aws s3 ls "s3://$DEPLOYMENT_BUCKET" 2>&1 > /dev/null; then
  echo "배포 버킷($DEPLOYMENT_BUCKET)이 이미 존재합니다. 이 버킷을 재사용합니다."
  # 스택 생성/업데이트 시 파라미터로 기존 버킷 사용 지시
  BUCKET_EXISTS="true"
else
  echo "배포 버킷($DEPLOYMENT_BUCKET)이 존재하지 않습니다. 새로 생성합니다."
  BUCKET_EXISTS="false"
fi

# OutputBucket 존재 여부 확인
if aws s3 ls "s3://$OUTPUT_BUCKET_NAME" 2>&1 > /dev/null; then
  echo "출력 버킷($OUTPUT_BUCKET_NAME)이 이미 존재합니다. 이 버킷을 재사용합니다."
  OUTPUT_BUCKET_EXISTS="true"
else
  echo "출력 버킷($OUTPUT_BUCKET_NAME)이 존재하지 않습니다. 새로 생성합니다."
  OUTPUT_BUCKET_EXISTS="false"
fi  # 이 부분이 누락되었습니다

# 기본 스택 배포
BASE_STACK_NAME="wga-base-$ENV"
echo "기본 인프라 스택 배포 중: $BASE_STACK_NAME..."

if aws cloudformation describe-stacks --stack-name $BASE_STACK_NAME 2>&1 > /dev/null; then
    # 스택이 존재하면 업데이트
    echo "기존 스택 업데이트 중: $BASE_STACK_NAME"
    aws cloudformation update-stack \
        --stack-name $BASE_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/base.yaml" \
        --parameters ParameterKey=Environment,ParameterValue=$ENV \
                    ParameterKey=BucketExists,ParameterValue=$BUCKET_EXISTS \
                    ParameterKey=OutputBucketExists,ParameterValue=$OUTPUT_BUCKET_EXISTS \
        --capabilities CAPABILITY_NAMED_IAM

    # 스택 업데이트 완료 대기
    echo "스택 업데이트 완료 대기 중: $BASE_STACK_NAME"
    aws cloudformation wait stack-update-complete --stack-name $BASE_STACK_NAME
else
    # 스택이 존재하지 않으면 생성
    echo "새 스택 생성 중: $BASE_STACK_NAME"
    aws cloudformation create-stack \
        --stack-name $BASE_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/base.yaml" \
        --parameters ParameterKey=Environment,ParameterValue=$ENV \
                    ParameterKey=BucketExists,ParameterValue=$BUCKET_EXISTS \
                    ParameterKey=OutputBucketExists,ParameterValue=$OUTPUT_BUCKET_EXISTS \
        --capabilities CAPABILITY_NAMED_IAM

    # 스택 생성 완료 대기
    echo "스택 생성 완료 대기 중: $BASE_STACK_NAME"
    aws cloudformation wait stack-create-complete --stack-name $BASE_STACK_NAME
fi

echo "기본 인프라 스택 배포 완료: $BASE_STACK_NAME"

# 배포 버킷이 이제 존재해야 함
echo "배포 버킷이 존재하는지 확인 중: $DEPLOYMENT_BUCKET"
if ! aws s3 ls "s3://$DEPLOYMENT_BUCKET" 2>&1 > /dev/null; then
    echo "배포 버킷이 없습니다. 기본 스택이 올바르게 생성되었는지 확인하세요."
    exit 1
fi

echo "====== Layer 및 Lambda 함수 패키징 ======"

# 빌드 디렉토리 정리 (이전 빌드 파일 제거)
echo "빌드 디렉토리 정리 중..."
rm -rf build
mkdir -p build

# Common 레이어 패키징 및 업로드
echo "Common 레이어 패키징 중..."
mkdir -p build/layers/python/common
mkdir -p build/layers/python/lib/python3.12/site-packages
cp -r layers/common/* build/layers/python/common/

echo "Common 레이어 의존성 설치 중..."
pip install -r layers/common/requirements.txt -t build/layers/python/lib/python3.12/site-packages/

cd build/layers
echo "Common 레이어 압축 중..."
zip -r common-layer-$ENV.zip python
cd ../..

# Layer 구조 확인
echo "Layer 구조 확인:"
unzip -l build/layers/common-layer-$ENV.zip | head -n 20

# Layer 압축 파일 내용 검증
if unzip -l build/layers/common-layer-$ENV.zip | grep -q "python/common/config.py"; then
  echo "Layer 구조가 올바릅니다."
else
  echo "경고: Layer 구조가 올바르지 않을 수 있습니다!"
  unzip -l build/layers/common-layer-$ENV.zip
fi

echo "Common 레이어 업로드 중..."
aws s3 cp build/layers/common-layer-$ENV.zip "s3://$DEPLOYMENT_BUCKET/layers/common-layer-$ENV.zip"

# Auth Lambda 패키징 및 업로드
echo "Auth Lambda 패키징 중..."
mkdir -p build/auth
cp -r services/auth/* build/auth/
cd build/auth
echo "Auth Lambda 압축 중..."
zip -r auth-lambda-$ENV.zip *
cd ../..

echo "Auth Lambda 업로드 중..."
aws s3 cp build/auth/auth-lambda-$ENV.zip "s3://$DEPLOYMENT_BUCKET/auth/auth-lambda-$ENV.zip"

# Security Analytics Lambda 패키징 및 업로드 (존재하는 경우)
if [ -d "services/security_analytics" ]; then
    echo "Security Analytics Lambda 패키징 중..."
    mkdir -p build/security_analytics
    cp -r services/security_analytics/* build/security_analytics/
    cd build/security_analytics
    echo "Security Analytics Lambda 압축 중..."
    zip -r security-analytics-lambda-$ENV.zip *
    cd ../..

    echo "Security Analytics Lambda 업로드 중..."
    aws s3 cp build/security_analytics/security-analytics-lambda-$ENV.zip "s3://$DEPLOYMENT_BUCKET/security_analytics/security-analytics-lambda-$ENV.zip"
fi

# Zero Trust Lambda 패키징 및 업로드 (존재하는 경우)
if [ -d "services/zero_trust" ]; then
    echo "Zero Trust Lambda 패키징 중..."
    mkdir -p build/zero_trust
    cp -r services/zero_trust/* build/zero_trust/
    cd build/zero_trust
    echo "Zero Trust Lambda 압축 중..."
    zip -r zero-trust-lambda-$ENV.zip *
    cd ../..

    echo "Zero Trust Lambda 업로드 중..."
    aws s3 cp build/zero_trust/zero-trust-lambda-$ENV.zip "s3://$DEPLOYMENT_BUCKET/zero_trust/zero-trust-lambda-$ENV.zip"
fi

echo "====== 메인 및 서비스 스택 배포 ======"
# 메인 스택 배포
MAIN_STACK_NAME="wga-$ENV"
echo "메인 스택 배포 중: $MAIN_STACK_NAME..."

DEVELOPER_MODE=${2:-true}  # 기본값: true

# 기본 스택에서 출력값 가져오기
echo "기본 스택에서 출력값 가져오는 중..."
USER_POOL_ID=$(aws cloudformation describe-stacks --stack-name $BASE_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)
USER_POOL_CLIENT_ID=$(aws cloudformation describe-stacks --stack-name $BASE_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" --output text)
USER_POOL_DOMAIN=$(aws cloudformation describe-stacks --stack-name $BASE_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='UserPoolDomain'].OutputValue" --output text)
IDENTITY_POOL_ID=$(aws cloudformation describe-stacks --stack-name $BASE_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='IdentityPoolId'].OutputValue" --output text)
OUTPUT_BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name $BASE_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='OutputBucketName'].OutputValue" --output text)
SECURITY_ALERTS_TOPIC_ARN=$(aws cloudformation describe-stacks --stack-name $BASE_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='SecurityAlertsTopicArn'].OutputValue" --output text)

echo "가져온 파라미터 확인:"
echo "USER_POOL_ID: $USER_POOL_ID"
echo "USER_POOL_CLIENT_ID: $USER_POOL_CLIENT_ID"
echo "USER_POOL_DOMAIN: $USER_POOL_DOMAIN"
echo "IDENTITY_POOL_ID: $IDENTITY_POOL_ID"
echo "OUTPUT_BUCKET_NAME: $OUTPUT_BUCKET_NAME"
echo "SECURITY_ALERTS_TOPIC_ARN: $SECURITY_ALERTS_TOPIC_ARN"

if aws cloudformation describe-stacks --stack-name $MAIN_STACK_NAME 2>&1 > /dev/null; then
    # 스택이 존재하면 업데이트
    echo "기존 스택 업데이트 중: $MAIN_STACK_NAME"
    aws cloudformation update-stack \
        --stack-name $MAIN_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/main.yaml" \
        --parameters \
            ParameterKey=Environment,ParameterValue=$ENV \
            ParameterKey=DeveloperMode,ParameterValue=$DEVELOPER_MODE \
            ParameterKey=UserPoolId,ParameterValue=$USER_POOL_ID \
            ParameterKey=UserPoolClientId,ParameterValue=$USER_POOL_CLIENT_ID \
            ParameterKey=UserPoolDomain,ParameterValue=$USER_POOL_DOMAIN \
            ParameterKey=IdentityPoolId,ParameterValue=$IDENTITY_POOL_ID \
            ParameterKey=OutputBucketName,ParameterValue=$OUTPUT_BUCKET_NAME \
            ParameterKey=SecurityAlertsTopicArn,ParameterValue=$SECURITY_ALERTS_TOPIC_ARN \
        --capabilities CAPABILITY_NAMED_IAM

    # 스택 업데이트 완료 대기
    echo "스택 업데이트 완료 대기 중: $MAIN_STACK_NAME"
    aws cloudformation wait stack-update-complete --stack-name $MAIN_STACK_NAME
else
    # 스택이 존재하지 않으면 생성
    echo "새 스택 생성 중: $MAIN_STACK_NAME"
    aws cloudformation create-stack \
        --stack-name $MAIN_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/main.yaml" \
        --parameters \
            ParameterKey=Environment,ParameterValue=$ENV \
            ParameterKey=DeveloperMode,ParameterValue=$DEVELOPER_MODE \
            ParameterKey=UserPoolId,ParameterValue=$USER_POOL_ID \
            ParameterKey=UserPoolClientId,ParameterValue=$USER_POOL_CLIENT_ID \
            ParameterKey=UserPoolDomain,ParameterValue=$USER_POOL_DOMAIN \
            ParameterKey=IdentityPoolId,ParameterValue=$IDENTITY_POOL_ID \
            ParameterKey=OutputBucketName,ParameterValue=$OUTPUT_BUCKET_NAME \
            ParameterKey=SecurityAlertsTopicArn,ParameterValue=$SECURITY_ALERTS_TOPIC_ARN \
        --capabilities CAPABILITY_NAMED_IAM

    # 스택 생성 완료 대기
    echo "스택 생성 완료 대기 중: $MAIN_STACK_NAME"
    aws cloudformation wait stack-create-complete --stack-name $MAIN_STACK_NAME
fi

echo "메인 스택 배포 완료: $MAIN_STACK_NAME"

# API Gateway URL 확인
API_URL=$(aws cloudformation describe-stacks --stack-name $MAIN_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text)
echo "API Gateway URL: $API_URL"

# Lambda 함수가 올바르게 배포되었는지 확인
echo "====== 배포 확인 ======"
echo "Auth Lambda 함수 설정 확인:"
aws lambda get-function --function-name wga-auth-$ENV --query "Configuration.[FunctionName,Layers]" --output json || echo "Auth Lambda 함수가 존재하지 않거나 접근할 수 없습니다."

if [ -d "services/security_analytics" ]; then
    echo "Security Analytics Lambda 함수 설정 확인:"
    aws lambda get-function --function-name wga-security-analytics-$ENV --query "Configuration.[FunctionName,Layers]" --output json || echo "Security Analytics Lambda 함수가 존재하지 않거나 접근할 수 없습니다."
fi

if [ -d "services/zero_trust" ]; then
    echo "Zero Trust Lambda 함수 설정 확인:"
    aws lambda get-function --function-name wga-zero-trust-enforcer-$ENV --query "Configuration.[FunctionName,Layers]" --output json || echo "Zero Trust Lambda 함수가 존재하지 않거나 접근할 수 없습니다."
fi

echo "배포가 완료되었습니다."
echo "ENV=$ENV DEVELOPER_MODE=$DEVELOPER_MODE"