#!/bin/bash
# WGA - 채팅 내역 저장 기능 배포 스크립트

# 오류 발생 시 스크립트 중단
set -e

# 환경 변수 설정
ENV=${1:-dev}  # 기본값: dev
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
REGION=$(aws configure get region)

echo "========================================"
echo "채팅 내역 저장 기능 배포 시작 - 환경: $ENV"
echo "AWS 계정 ID: $ACCOUNT_ID"
echo "AWS 리전: $REGION"
echo "========================================"

# 배포 버킷 이름
CLOUDFORMATION_BUCKET="wga-cloudformation-$ACCOUNT_ID"
DEPLOYMENT_BUCKET="wga-deployment-$ENV"

# 스택 이름 설정
CHAT_DB_STACK_NAME="wga-chat-db-$ENV"
CHAT_HISTORY_STACK_NAME="wga-chat-history-$ENV"

# 1. CloudFormation 템플릿 업로드
echo "CloudFormation 템플릿 업로드 중..."
aws s3 cp cloudformation/chat-db.yaml "s3://$CLOUDFORMATION_BUCKET/chat-db.yaml"
aws s3 cp cloudformation/chat-history.yaml "s3://$CLOUDFORMATION_BUCKET/chat-history.yaml"
echo "CloudFormation 템플릿 업로드 완료"

# 2. DynamoDB 테이블 배포
echo "채팅 내역 DB 스택 배포 중: $CHAT_DB_STACK_NAME..."

if aws cloudformation describe-stacks --stack-name "$CHAT_DB_STACK_NAME" > /dev/null 2>&1; then
    # 스택이 존재하면 업데이트
    echo "기존 스택 업데이트 중: $CHAT_DB_STACK_NAME"
    aws cloudformation update-stack \
        --stack-name $CHAT_DB_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/chat-db.yaml" \
        --parameters ParameterKey=Environment,ParameterValue=$ENV \
        --capabilities CAPABILITY_NAMED_IAM \
        || echo "No updates to be performed."

    # 스택 업데이트 완료 대기
    if [ $? -eq 0 ]; then
        echo "스택 업데이트 완료 대기 중: $CHAT_DB_STACK_NAME"
        aws cloudformation wait stack-update-complete --stack-name $CHAT_DB_STACK_NAME
    fi
else
    # 스택이 존재하지 않으면 생성
    echo "새 스택 생성 중: $CHAT_DB_STACK_NAME"
    aws cloudformation create-stack \
        --stack-name $CHAT_DB_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/chat-db.yaml" \
        --parameters ParameterKey=Environment,ParameterValue=$ENV \
        --capabilities CAPABILITY_NAMED_IAM

    # 스택 생성 완료 대기
    echo "스택 생성 완료 대기 중: $CHAT_DB_STACK_NAME"
    aws cloudformation wait stack-create-complete --stack-name $CHAT_DB_STACK_NAME
fi

echo "채팅 내역 DB 스택 배포 완료: $CHAT_DB_STACK_NAME"

# 3. Lambda 패키징 및 업로드
echo "채팅 내역 Lambda 패키징 중..."
mkdir -p build/chat-history
cp -r services/chat-history/* build/chat-history/
cd build/chat-history
echo "Lambda 압축 중..."
zip -r chat-history-lambda-$ENV.zip *
cd ../..

echo "Lambda 업로드 중..."
aws s3 cp build/chat-history/chat-history-lambda-$ENV.zip "s3://$DEPLOYMENT_BUCKET/chat-history/chat-history-lambda-$ENV.zip"

# 4. API Gateway와 Lambda 연결
echo "채팅 내역 API 스택 배포 중: $CHAT_HISTORY_STACK_NAME..."

# 필요한 정보 가져오기
API_GATEWAY_ID=$(aws ssm get-parameter --name "/wga/$ENV/ApiGatewayId" --query "Parameter.Value" --output text)
API_GATEWAY_ROOT_RESOURCE_ID=$(aws ssm get-parameter --name "/wga/$ENV/ApiGatewayRootResourceId" --query "Parameter.Value" --output text)
FRONTEND_REDIRECT_DOMAIN=$(aws ssm get-parameter --name "/wga/$ENV/FrontendRedirectDomain" --query "Parameter.Value" --output text)

echo "API Gateway ID: $API_GATEWAY_ID"
echo "API Gateway Root Resource ID: $API_GATEWAY_ROOT_RESOURCE_ID"
echo "Frontend Redirect Domain: $FRONTEND_REDIRECT_DOMAIN"

if aws cloudformation describe-stacks --stack-name "$CHAT_HISTORY_STACK_NAME" > /dev/null 2>&1; then
    # 스택이 존재하면 업데이트
    echo "기존 스택 업데이트 중: $CHAT_HISTORY_STACK_NAME"
    aws cloudformation update-stack \
        --stack-name $CHAT_HISTORY_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/chat-history.yaml" \
        --parameters \
            ParameterKey=Environment,ParameterValue=$ENV \
            ParameterKey=ApiGatewayId,ParameterValue=$API_GATEWAY_ID \
            ParameterKey=ApiGatewayRootResourceId,ParameterValue=$API_GATEWAY_ROOT_RESOURCE_ID \
            ParameterKey=FrontendRedirectDomain,ParameterValue=$FRONTEND_REDIRECT_DOMAIN \
        --capabilities CAPABILITY_NAMED_IAM \
        || echo "No updates to be performed."

    # 스택 업데이트 완료 대기
    if [ $? -eq 0 ]; then
        echo "스택 업데이트 완료 대기 중: $CHAT_HISTORY_STACK_NAME"
        aws cloudformation wait stack-update-complete --stack-name $CHAT_HISTORY_STACK_NAME
    fi
else
    # 스택이 존재하지 않으면 생성
    echo "새 스택 생성 중: $CHAT_HISTORY_STACK_NAME"
    aws cloudformation create-stack \
        --stack-name $CHAT_HISTORY_STACK_NAME \
        --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/chat-history.yaml" \
        --parameters \
            ParameterKey=Environment,ParameterValue=$ENV \
            ParameterKey=ApiGatewayId,ParameterValue=$API_GATEWAY_ID \
            ParameterKey=ApiGatewayRootResourceId,ParameterValue=$API_GATEWAY_ROOT_RESOURCE_ID \
            ParameterKey=FrontendRedirectDomain,ParameterValue=$FRONTEND_REDIRECT_DOMAIN \
        --capabilities CAPABILITY_NAMED_IAM

    # 스택 생성 완료 대기
    echo "스택 생성 완료 대기 중: $CHAT_HISTORY_STACK_NAME"
    aws cloudformation wait stack-create-complete --stack-name $CHAT_HISTORY_STACK_NAME
fi

echo "채팅 내역 API 스택 배포 완료: $CHAT_HISTORY_STACK_NAME"

# 5. API 설정 요약 출력
CHAT_HISTORY_API_URL=$(aws cloudformation describe-stacks --stack-name $CHAT_HISTORY_STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='ChatHistoryApiUrl'].OutputValue" --output text)

echo "========================================="
echo "배포 완료!"
echo "Chat History API URL: $CHAT_HISTORY_API_URL"
echo "========================================="

# 6. 프론트엔드 빌드 및 배포
echo "프론트엔드 파일 복사 중..."
mkdir -p frontend/src/services
mkdir -p frontend/src/stores
mkdir -p frontend/src/helpers

# 새 파일 복사
cp -f build/chat-api-service.ts frontend/src/services/
cp -f build/chatbotWithPersistence.ts frontend/src/stores/
cp -f build/initializeAuth.ts frontend/src/helpers/

echo "main.ts 업데이트 확인"
# main.ts를 사용하여 기본 스토어 대신 채팅 내역 저장 스토어 사용

echo "프론트엔드 빌드 및 배포는 별도로 진행해주세요."
echo "다음 명령을 실행하세요:"
echo "  cd frontend"
echo "  npm install"
echo "  npm run build"
echo "  cd .."
echo "  ./deploy.sh $ENV"

echo "배포 완료!"