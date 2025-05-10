#!/bin/bash
# WGA - ChatHistory 배포 스크립트

# 오류 발생 시 스크립트 중단
set -e

# 환경 변수 설정
ENV=${1:-dev}  # 기본값: dev
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
REGION=$(aws configure get region)
MCP_IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/wga-mcp-$ENV:latest"

echo "========================================"
echo "ChatHistory 배포 시작 - 환경: $ENV"
echo "AWS 계정 ID: $ACCOUNT_ID"
echo "AWS 리전: $REGION"
echo "========================================"

# 배포 버킷 이름
CLOUDFORMATION_BUCKET="wga-cloudformation-$ACCOUNT_ID"
DEPLOYMENT_BUCKET="wga-deployment-$ENV"

# ChatHistory 템플릿 업로드
echo "ChatHistory CloudFormation 템플릿 업로드 중..."
aws s3 cp cloudformation/chat-history.yaml "s3://$CLOUDFORMATION_BUCKET/chat-history.yaml"
aws s3 cp cloudformation/main.yaml "s3://$CLOUDFORMATION_BUCKET/main.yaml"
echo "CloudFormation 템플릿 업로드 완료"

# ChatHistory Lambda 패키징 및 업로드
echo "====== ChatHistory Lambda 패키징 ======"
mkdir -p build/chat-history
cp -r services/chat-history/* build/chat-history/

cd build/chat-history
echo "ChatHistory Lambda 압축 중..."
zip -r chat-history-lambda-$ENV.zip *
cd ../..

echo "ChatHistory Lambda 업로드 중..."
aws s3 cp build/chat-history/chat-history-lambda-$ENV.zip "s3://$DEPLOYMENT_BUCKET/chat-history/chat-history-lambda-$ENV.zip"

# SSM 파라미터 경로 기본 prefix 설정
SSM_PATH_PREFIX="/wga/$ENV"

# 기본 스택에서 출력값 가져오기
echo "기본 스택에서 출력값 가져오는 중..."
API_GATEWAY_ID=$(aws ssm get-parameter --name "$SSM_PATH_PREFIX/ApiGatewayId" --query "Parameter.Value" --output text)
API_GATEWAY_ROOT_RESOURCE_ID=$(aws ssm get-parameter --name "$SSM_PATH_PREFIX/ApiGatewayRootResourceId" --query "Parameter.Value" --output text)
FRONTEND_REDIRECT_DOMAIN=$(aws ssm get-parameter --name "$SSM_PATH_PREFIX/FrontendRedirectDomain" --query "Parameter.Value" --output text)

echo "가져온 파라미터 확인:"
echo "API_GATEWAY_ID: $API_GATEWAY_ID"
echo "API_GATEWAY_ROOT_RESOURCE_ID: $API_GATEWAY_ROOT_RESOURCE_ID"
echo "FRONTEND_REDIRECT_DOMAIN: $FRONTEND_REDIRECT_DOMAIN"

# 메인 스택 업데이트
echo "====== 메인 스택 업데이트 ======"

# McpFunctionUrl 가져오기
McpFunctionUrl=$(aws lambda get-function-url-config \
  --function-name wga-mcp-$ENV \
  --query "FunctionUrl" \
  --output text 2>/dev/null || echo "placeholder")

echo "메인 스택 업데이트 중..."
aws cloudformation update-stack \
    --stack-name wga-$ENV \
    --template-url "https://s3.amazonaws.com/$CLOUDFORMATION_BUCKET/main.yaml" \
    --parameters \
        ParameterKey=Environment,ParameterValue=$ENV \
        ParameterKey=DeveloperMode,ParameterValue=true \
        ParameterKey=UserPoolId,ParameterValue="$SSM_PATH_PREFIX/UserPoolId" \
        ParameterKey=UserPoolClientId,ParameterValue="$SSM_PATH_PREFIX/UserPoolClientId" \
        ParameterKey=UserPoolDomain,ParameterValue="$SSM_PATH_PREFIX/UserPoolDomain" \
        ParameterKey=IdentityPoolId,ParameterValue="$SSM_PATH_PREFIX/IdentityPoolId" \
        ParameterKey=OutputBucketName,ParameterValue="$SSM_PATH_PREFIX/OutputBucketName" \
        ParameterKey=ApiGatewayIdParameter,ParameterValue="$SSM_PATH_PREFIX/ApiGatewayId" \
        ParameterKey=ApiGatewayRootResourceIdParameter,ParameterValue="$SSM_PATH_PREFIX/ApiGatewayRootResourceId" \
        ParameterKey=FrontendRedirectDomainParameter,ParameterValue="$SSM_PATH_PREFIX/FrontendRedirectDomain" \
        ParameterKey=SlackBotTokenSSMPathParameter,ParameterValue="$SSM_PATH_PREFIX/SlackbotToken" \
        ParameterKey=AthenaOutputBucketParameter,ParameterValue="$SSM_PATH_PREFIX/AthenaOutputBucketName" \
        ParameterKey=KnowledgeBaseIdParameter,ParameterValue="$SSM_PATH_PREFIX/KnowledgeBaseId" \
        ParameterKey=McpImageUri,ParameterValue=$MCP_IMAGE_URI \
    --capabilities CAPABILITY_NAMED_IAM

echo "메인 스택 업데이트 대기 중..."
aws cloudformation wait stack-update-complete --stack-name wga-$ENV
echo "메인 스택 업데이트 완료"

# API Gateway URL 확인
API_URL="https://${API_GATEWAY_ID}.execute-api.${REGION}.amazonaws.com/${ENV}"
echo "API Gateway URL: $API_URL"

echo "===== ChatHistory 배포 완료! ====="
echo "다음 API 엔드포인트가 사용 가능합니다:"
echo "세션 생성: POST $API_URL/sessions"
echo "세션 목록 조회: GET $API_URL/sessions?userId={userId}"
echo "세션 조회: GET $API_URL/sessions/{sessionId}"
echo "세션 업데이트: PUT $API_URL/sessions/{sessionId}"
echo "세션 삭제: DELETE $API_URL/sessions/{sessionId}"
echo "메시지 추가: POST $API_URL/sessions/{sessionId}/messages"
echo "메시지 조회: GET $API_URL/sessions/{sessionId}/messages"
echo "==============================="