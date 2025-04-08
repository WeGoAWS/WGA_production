#!/bin/bash
# WGA - 통합 배포 스크립트 (백엔드 + 프론트엔드)

# 오류 발생 시 스크립트 중단
set -e

# 환경 변수 설정
ENV=${1:-dev}  # 기본값: dev
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
REGION=$(aws configure get region)

echo "========================================"
echo "통합 배포 시작 - 환경: $ENV"
echo "AWS 계정 ID: $ACCOUNT_ID"
echo "AWS 리전: $REGION"
echo "백엔드 배포 스킵: $SKIP_BACKEND"
echo "프론트엔드 배포 스킵: $SKIP_FRONTEND"
echo "========================================"

# 배포 버킷 이름
CLOUDFORMATION_BUCKET="wga-cloudformation-$ACCOUNT_ID"
DEPLOYMENT_BUCKET="wga-deployment-$ENV"
FRONTEND_BUCKET="wga-frontend-$ENV"
OUTPUT_BUCKET_NAME="wga-outputbucket-$ENV"

# 스택 이름 설정
BASE_STACK_NAME="wga-base-$ENV"
MAIN_STACK_NAME="wga-$ENV"
FRONTEND_STACK_NAME="wga-frontend-$ENV"

# 도메인 설정 (필요한 경우 수정)
DOMAIN_NAME=""  # 사용자 정의 도메인
CERTIFICATE_ARN=""  # 사용자 정의 도메인에 필요한 ACM 인증서 ARN
if [ "$ENV" = "dev" ]; then
  DEVELOPER_MODE=true
else
  DEVELOPER_MODE=false
fi

# SSM 파라미터 경로 기본 prefix 설정
SSM_PATH_PREFIX="/wga/$ENV"

#################################################
# 1. CloudFormation 버킷 확인 및 템플릿 업로드
#################################################
echo "CloudFormation 템플릿을 저장할 $CLOUDFORMATION_BUCKET 버킷 확인 중..."
if ! aws s3 ls "s3://$CLOUDFORMATION_BUCKET" 2>&1 > /dev/null; then
    echo "$CLOUDFORMATION_BUCKET 버킷이 존재하지 않습니다. 생성합니다..."
    aws s3 mb "s3://$CLOUDFORMATION_BUCKET" --region $REGION
    aws s3api put-bucket-versioning --bucket "$CLOUDFORMATION_BUCKET" --versioning-configuration Status=Enabled
    echo "$CLOUDFORMATION_BUCKET 버킷 생성 완료"
else
    echo "$CLOUDFORMATION_BUCKET 버킷이 이미 존재합니다"
fi

echo "====== 1. CloudFormation 템플릿 업로드 ======"
# 배포 버킷이 존재하지 않을 수 있으므로 base 스택을 먼저 배포
echo "CloudFormation 템플릿 업로드 중..."
aws s3 cp cloudformation/base.yaml "s3://$CLOUDFORMATION_BUCKET/base.yaml"
aws s3 cp cloudformation/llm.yaml "s3://$CLOUDFORMATION_BUCKET/llm.yaml"
aws s3 cp cloudformation/main.yaml "s3://$CLOUDFORMATION_BUCKET/main.yaml"
aws s3 cp cloudformation/frontend.yaml "s3://$CLOUDFORMATION_BUCKET/frontend.yaml"

echo "CloudFormation 템플릿 업로드 완료"

#################################################
# 2. 기본 스택 배포
#################################################
echo "====== 2. 기본 스택 배포 시작 ======"

# 기본 스택 배포 전 S3 버킷 존재 여부 확인
if aws s3 ls "s3://$DEPLOYMENT_BUCKET" > /dev/null 2>&1; then
    echo "배포 버킷($DEPLOYMENT_BUCKET)이 이미 존재합니다. 이 버킷을 재사용합니다."
    BUCKET_EXISTS="true"
    echo "$DEPLOYMENT_BUCKET 버킷 내용을 정리합니다..."
    aws s3 rm "s3://$DEPLOYMENT_BUCKET" --recursive
else
    echo "배포 버킷($DEPLOYMENT_BUCKET)이 존재하지 않습니다. 새로 생성합니다."
    BUCKET_EXISTS="false"
fi

# OutputBucket 존재 여부 확인
if aws s3 ls "s3://$OUTPUT_BUCKET_NAME" > /dev/null 2>&1; then
    echo "출력 버킷($OUTPUT_BUCKET_NAME)이 이미 존재합니다. 이 버킷을 재사용합니다."
    OUTPUT_BUCKET_EXISTS="true"
    echo "$OUTPUT_BUCKET_NAME 버킷 내용을 정리합니다..."
    aws s3 rm "s3://$OUTPUT_BUCKET_NAME" --recursive
else
    echo "출력 버킷($OUTPUT_BUCKET_NAME)이 존재하지 않습니다. 새로 생성합니다."
    OUTPUT_BUCKET_EXISTS="false"
fi

# 프론트엔드 버킷 존재 여부 확인
if aws s3 ls "s3://$FRONTEND_BUCKET" > /dev/null 2>&1; then
    echo "출력 버킷($FRONTEND_BUCKET)이 이미 존재합니다. 이 버킷을 재사용합니다."
    echo "$FRONTEND_BUCKET 버킷 내용을 정리합니다..."
    aws s3 rm "s3://$FRONTEND_BUCKET" --recursive
fi

# 기본 스택 배포
echo "기본 인프라 스택 배포 중: $BASE_STACK_NAME..."

if aws cloudformation describe-stacks --stack-name "$BASE_STACK_NAME" > /dev/null 2>&1; then
    # 스택이 존재하면 업데이트
    echo "기존 스택 업데이트 중: $BASE_STACK_NAME"
    aws cloudformation update-stack \
        --stack-name $BASE_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/base.yaml" \
        --parameters ParameterKey=Environment,ParameterValue=$ENV \
                    ParameterKey=BucketExists,ParameterValue=$BUCKET_EXISTS \
                    ParameterKey=OutputBucketExists,ParameterValue=$OUTPUT_BUCKET_EXISTS \
                    ParameterKey=FrontendRedirectDomain,ParameterValue=placeholder.example.com \
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
                    ParameterKey=FrontendRedirectDomain,ParameterValue=placeholder.example.com \
        --capabilities CAPABILITY_NAMED_IAM

    # 스택 생성 완료 대기
    echo "스택 생성 완료 대기 중: $BASE_STACK_NAME"
    aws cloudformation wait stack-create-complete --stack-name $BASE_STACK_NAME
fi

echo "기본 인프라 스택 배포 완료: $BASE_STACK_NAME"

# 배포 버킷이 이제 존재해야 함
echo "배포 버킷이 존재하는지 확인 중: $DEPLOYMENT_BUCKET"
if ! aws s3 ls "s3://$DEPLOYMENT_BUCKET" > /dev/null 2>&1; then
    echo "배포 버킷이 없습니다. 기본 스택이 올바르게 생성되었는지 확인하세요."
    exit 1
fi

#################################################
# 3. 프론트엔드 인프라 배포
#################################################
# 프론트엔드 스택 배포
echo "====== 3. 프론트엔드 인프라 배포 ======"
echo "프론트엔드 인프라 스택 배포 중: $FRONTEND_STACK_NAME..."

# 도메인 설정에 대한 정보 표시
if [ -n "$DOMAIN_NAME" ] && [ -n "$CERTIFICATE_ARN" ]; then
    echo "사용자 정의 도메인: $DOMAIN_NAME (인증서: $CERTIFICATE_ARN)"
fi

if aws cloudformation describe-stacks --stack-name $FRONTEND_STACK_NAME > /dev/null 2>&1; then
    # 스택이 존재하면 업데이트
    echo "기존 프론트엔드 스택 업데이트 중: $FRONTEND_STACK_NAME"
    aws cloudformation update-stack \
        --stack-name $FRONTEND_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/frontend.yaml" \
        --parameters \
            ParameterKey=Environment,ParameterValue=$ENV \
            ParameterKey=DomainName,ParameterValue=$DOMAIN_NAME \
            ParameterKey=CertificateARN,ParameterValue=$CERTIFICATE_ARN \
        --capabilities CAPABILITY_NAMED_IAM

    # 스택 업데이트 완료 대기
    echo "프론트엔드 스택 업데이트 완료 대기 중: $FRONTEND_STACK_NAME"
    aws cloudformation wait stack-update-complete --stack-name $FRONTEND_STACK_NAME
else
    # 스택이 존재하지 않으면 생성
    echo "새 프론트엔드 스택 생성 중: $FRONTEND_STACK_NAME"
    aws cloudformation create-stack \
        --stack-name $FRONTEND_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/frontend.yaml" \
        --parameters \
            ParameterKey=Environment,ParameterValue=$ENV \
            ParameterKey=DomainName,ParameterValue=$DOMAIN_NAME \
            ParameterKey=CertificateARN,ParameterValue=$CERTIFICATE_ARN \
        --capabilities CAPABILITY_NAMED_IAM

    # 스택 생성 완료 대기
    echo "프론트엔드 스택 생성 완료 대기 중: $FRONTEND_STACK_NAME"
    aws cloudformation wait stack-create-complete --stack-name $FRONTEND_STACK_NAME
fi

echo "프론트엔드 인프라 스택 배포 완료: $FRONTEND_STACK_NAME"

# 프론트엔드 배포 정보 가져오기
AMPLIFY_APP_ID=$(aws cloudformation describe-stacks --stack-name $FRONTEND_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='AmplifyAppId'].OutputValue" --output text)
FRONTEND_URL=$(aws cloudformation describe-stacks --stack-name $FRONTEND_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='AmplifyAppDefaultDomain'].OutputValue" --output text)

echo "프론트엔드 배포 정보:"
echo "Amplify App ID: $AMPLIFY_APP_ID"
echo "Amplify 기본 도메인: https://$FRONTEND_URL"

# FrontendRedirectDomain 정보를 SSM에 업데이트
echo "FrontendRedirectDomain 값을 SSM에 업데이트 중..."
aws ssm put-parameter \
    --name "$SSM_PATH_PREFIX/FrontendRedirectDomain" \
    --value "$FRONTEND_URL" \
    --type "String" \
    --overwrite

# SSM 파라미터 변경 후 base 스택 업데이트 (SSM 파라미터가 CloudFormation에 의해 생성되기 때문)
echo "FrontendRedirectDomain 업데이트를 위해 base 스택 업데이트 중..."
aws cloudformation update-stack \
    --stack-name $BASE_STACK_NAME \
    --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/base.yaml" \
    --parameters ParameterKey=Environment,ParameterValue=$ENV \
                ParameterKey=BucketExists,ParameterValue=true \
                ParameterKey=OutputBucketExists,ParameterValue=true \
                ParameterKey=FrontendRedirectDomain,ParameterValue=$FRONTEND_URL \
    --capabilities CAPABILITY_NAMED_IAM

aws cloudformation wait stack-update-complete --stack-name $BASE_STACK_NAME
echo "FrontendRedirectDomain 업데이트 완료"

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

# LLM Lambda 패키징 및 업로드 (존재하는 경우)
if [ -d "services/llm" ]; then
    echo "LLM Lambda 패키징 중..."
    mkdir -p build/llm
    cp -r services/llm/* build/llm/
    cd build/llm
    echo "LLM Lambda 압축 중..."
    zip -r llm-lambda-$ENV.zip *
    cd ../..

    echo "LLM 업로드 중..."
    aws s3 cp build/llm/llm-lambda-$ENV.zip "s3://$DEPLOYMENT_BUCKET/llm/llm-lambda-$ENV.zip"
fi

# 기본 스택에서 출력값 가져오기
echo "기본 스택에서 출력값 가져오는 중..."
API_GATEWAY_ID=$(aws cloudformation describe-stacks --stack-name $BASE_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayId'].OutputValue" --output text)
API_GATEWAY_ROOT_RESOURCE_ID=$(aws cloudformation describe-stacks --stack-name $BASE_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayRootResourceId'].OutputValue" --output text)
FRONTEND_REDIRECT_DOMAIN=$(aws cloudformation describe-stacks --stack-name $BASE_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='FrontendRedirectDomain'].OutputValue" --output text)

echo "가져온 파라미터 확인:"
echo "API_GATEWAY_ID: $API_GATEWAY_ID"
echo "API_GATEWAY_ROOT_RESOURCE_ID: $API_GATEWAY_ROOT_RESOURCE_ID"
echo "FRONTEND_REDIRECT_DOMAIN: $FRONTEND_REDIRECT_DOMAIN"

# 메인 스택 배포 부분 수정
if aws cloudformation describe-stacks --stack-name $MAIN_STACK_NAME > /dev/null 2>&1; then
    # 스택이 존재하면 업데이트
    echo "기존 스택 업데이트 중: $MAIN_STACK_NAME"
    aws cloudformation update-stack \
        --stack-name $MAIN_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/main.yaml" \
        --parameters \
            ParameterKey=Environment,ParameterValue=$ENV \
            ParameterKey=DeveloperMode,ParameterValue=$DEVELOPER_MODE \
            ParameterKey=UserPoolId,ParameterValue="$SSM_PATH_PREFIX/UserPoolId" \
            ParameterKey=UserPoolClientId,ParameterValue="$SSM_PATH_PREFIX/UserPoolClientId" \
            ParameterKey=UserPoolDomain,ParameterValue="$SSM_PATH_PREFIX/UserPoolDomain" \
            ParameterKey=IdentityPoolId,ParameterValue="$SSM_PATH_PREFIX/IdentityPoolId" \
            ParameterKey=OutputBucketName,ParameterValue="$SSM_PATH_PREFIX/OutputBucketName" \
            ParameterKey=ApiGatewayIdParameter,ParameterValue="$SSM_PATH_PREFIX/ApiGatewayId" \
            ParameterKey=ApiGatewayRootResourceIdParameter,ParameterValue="$SSM_PATH_PREFIX/ApiGatewayRootResourceId" \
            ParameterKey=FrontendRedirectDomainParameter,ParameterValue="$SSM_PATH_PREFIX/FrontendRedirectDomain" \
        --capabilities CAPABILITY_NAMED_IAM
else
    # 스택이 존재하지 않으면 생성
    echo "새 스택 생성 중: $MAIN_STACK_NAME"
    aws cloudformation create-stack \
        --stack-name $MAIN_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/main.yaml" \
        --parameters \
            ParameterKey=Environment,ParameterValue=$ENV \
            ParameterKey=DeveloperMode,ParameterValue=$DEVELOPER_MODE \
            ParameterKey=UserPoolId,ParameterValue="$SSM_PATH_PREFIX/UserPoolId" \
            ParameterKey=UserPoolClientId,ParameterValue="$SSM_PATH_PREFIX/UserPoolClientId" \
            ParameterKey=UserPoolDomain,ParameterValue="$SSM_PATH_PREFIX/UserPoolDomain" \
            ParameterKey=IdentityPoolId,ParameterValue="$SSM_PATH_PREFIX/IdentityPoolId" \
            ParameterKey=OutputBucketName,ParameterValue="$SSM_PATH_PREFIX/OutputBucketName" \
            ParameterKey=ApiGatewayIdParameter,ParameterValue="$SSM_PATH_PREFIX/ApiGatewayId" \
            ParameterKey=ApiGatewayRootResourceIdParameter,ParameterValue="$SSM_PATH_PREFIX/ApiGatewayRootResourceId" \
            ParameterKey=FrontendRedirectDomainParameter,ParameterValue="$SSM_PATH_PREFIX/FrontendRedirectDomain" \
        --capabilities CAPABILITY_NAMED_IAM
fi

echo "메인 스택 배포 완료: $MAIN_STACK_NAME"

# API Gateway URL 확인 (CloudFormation Output 대신 SSM 기반으로 구성)
API_GATEWAY_ID=$(aws ssm get-parameter --name "$SSM_PATH_PREFIX/ApiGatewayId" --query "Parameter.Value" --output text)
API_URL="https://${API_GATEWAY_ID}.execute-api.${REGION}.amazonaws.com/${ENV}"
echo "API Gateway URL: $API_URL"

# API Endpoint SSM에 저장
echo "API Endpoint를 SSM에 저장 중..."
aws ssm put-parameter \
    --name "$SSM_PATH_PREFIX/ApiEndpoint" \
    --value "$API_URL" \
    --type "String" \
    --overwrite

if [ -d "services/llm" ]; then
    echo "LLM Lambda 함수 설정 확인:"
    aws lambda get-function --function-name wga-llm-$ENV --query "Configuration.[FunctionName,Layers]" --output json || echo "LLM Lambda 함수가 존재하지 않거나 접근할 수 없습니다."
fi

#################################################
# 4. 환경 변수 설정
#################################################
echo "====== 4. 환경 변수 설정 ======"
# SSM 파라미터에서 값을 가져옴
echo "[INFO] SSM에서 구성 값을 가져옵니다."
USER_POOL_ID=$(aws ssm get-parameter --name "$SSM_PATH_PREFIX/UserPoolId" --query "Parameter.Value" --output text)
USER_POOL_CLIENT_ID=$(aws ssm get-parameter --name "$SSM_PATH_PREFIX/UserPoolClientId" --query "Parameter.Value" --output text)
USER_POOL_DOMAIN=$(aws ssm get-parameter --name "$SSM_PATH_PREFIX/UserPoolDomain" --query "Parameter.Value" --output text)
IDENTITY_POOL_ID=$(aws ssm get-parameter --name "$SSM_PATH_PREFIX/IdentityPoolId" --query "Parameter.Value" --output text)
API_URL=$(aws ssm get-parameter --name "$SSM_PATH_PREFIX/ApiEndpoint" --query "Parameter.Value" --output text)

ENV_FILE="frontend/.env.local"

echo "환경 파일 생성 중: $ENV_FILE"

cat <<EOF > $ENV_FILE
AWS_REGION=$REGION
API_URL=/api
API_DEST=$API_URL

VITE_API_URL=/api
VITE_API_DEST=$API_URL

COGNITO_DOMAIN=$(echo "$USER_POOL_DOMAIN" | sed -E 's#https://([^.]*)\..*#\1#')
COGNITO_CLIENT_ID=$USER_POOL_CLIENT_ID
COGNITO_CLIENT_SECRET=
COGNITO_REDIRECT_URI=https://${FRONTEND_URL}/redirect
COGNITO_IDENTITY_POOL_ID=$IDENTITY_POOL_ID
USER_POOL_ID=$USER_POOL_ID
EOF

echo "환경 파일($ENV_FILE)이 업데이트되었습니다."

#################################################
# 5. 프론트엔드 빌드 및 배포
#################################################
echo "====== 5. 프론트엔드 빌드 및 배포 ======"

# frontend 디렉토리로 이동
cd frontend

# 빌드 디렉토리 설정
BUILD_DIR="dist"

echo "의존성 설치 중..."
npm install

echo "프로젝트 빌드 중..."
npm run build

if [ ! -d "$BUILD_DIR" ]; then
    echo "빌드 디렉토리($BUILD_DIR)가 존재하지 않습니다. 빌드가 실패했습니다."
    exit 1
fi

echo "Amplify에 S3 업로드 중..."
aws s3 sync dist s3://wga-frontend-$ENV --delete
  # Amplify에 S3 업로드 이후 수동 배포 트리거
  echo "Amplify 수동 배포 트리거 중..."
  TIMESTAMP=$(date +%s)
  S3_DEPLOY_PATH="s3://wga-frontend-$ENV/amplify-upload-$TIMESTAMP/"

  # 업로드한 dist 디렉토리를 복사 (원본 경로를 분리된 위치로 저장)
  aws s3 cp --recursive dist "$S3_DEPLOY_PATH"

  # Amplify 수동 배포 시작
  aws amplify start-deployment \
    --app-id "$AMPLIFY_APP_ID" \
    --branch-name main \
    --source-url "$S3_DEPLOY_PATH" \
    --source-url-type BUCKET_PREFIX

  echo "Amplify 배포 요청 완료"
echo "Amplify 배포 완료"

# 기존 디렉토리로 돌아감
cd ..

#################################################
# 6. 배포 완료 요약
echo "====== 6. 배포 완료 요약 ======"
echo "환경: $ENV"

if [ "$SKIP_BACKEND" != "true" ]; then
    echo "백엔드 배포 상태: 성공"
    echo "API URL: $API_URL"
else
    echo "백엔드 배포 상태: 스킵됨"
fi

if [ "$SKIP_FRONTEND" != "true" ]; then
    echo "프론트엔드 배포 상태: 성공"
    echo "프론트엔드 URL: $FRONTEND_URL"
else
    echo "프론트엔드 배포 상태: 스킵됨"
fi

# SSM 파라미터 요약 출력
echo "====== SSM 파라미터 요약 ======"
aws ssm get-parameters-by-path \
    --path "$SSM_PATH_PREFIX" \
    --query "Parameters[*].[Name,Value]" \
    --output table

echo "====== 배포 완료! ======"
echo "배포 시간: $(date)"
echo "감사합니다!"