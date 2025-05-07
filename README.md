# WGA (WeGoAWS) 프로젝트

이 프로젝트는 AWS 서비스를 활용한 완전 관리형 웹 애플리케이션 인프라를 구축합니다. CloudFormation을 사용하여 AWS 리소스를 정의하고 배포하는 Infrastructure as Code(IaC) 아키텍처를 구현했습니다.

## 아키텍처 개요

이 프로젝트는 다음과 같은 AWS 서비스를 사용합니다:

- **CloudFormation**: 인프라 스택 정의 및 배포
- **Amazon Cognito**: 사용자 인증 및 권한 관리
- **AWS Amplify**: 프론트엔드 호스팅 및 배포
- **AWS Lambda**: 서버리스 백엔드 로직 처리
- **Amazon API Gateway**: REST API 엔드포인트 제공
- **Amazon S3**: 정적 파일 저장 및 배포 아티팩트 관리
- **AWS Systems Manager Parameter Store**: 환경 변수 및 구성 관리
- **Amazon DynamoDB**: 데이터 저장 (코드에서 참조됨)
- **Amazon Bedrock**: LLM 추론 기능 제공

## 프로젝트 구조

```
.
├── cloudformation/         # CloudFormation 템플릿
│   ├── base.yaml           # 기본 인프라 (S3, Cognito, API Gateway 등)
│   ├── frontend.yaml       # 프론트엔드 인프라 (Amplify)
│   ├── llm.yaml            # LLM 서비스 인프라 (Lambda)
│   └── main.yaml           # 메인 템플릿 (다른 스택 참조)
├── layers/                 # Lambda 레이어
│   └── common/             # 공통 유틸리티 레이어
│       ├── config.py       # 설정 관리
│       ├── db.py           # 데이터베이스 인터페이스
│       ├── requirements.txt # 레이어 의존성
│       └── utils.py        # 유틸리티 함수
├── services/               # 백엔드 서비스
│   └── llm/                # LLM 서비스
│       ├── lambda_function.py # Lambda 핸들러
│       └── llm_service.py  # LLM 비즈니스 로직
└── deploy.sh               # 배포 스크립트
```

## CloudFormation 스택 구조

이 프로젝트는 여러 CloudFormation 스택으로 구성되어 있으며, 각 스택은 특정 기능을 담당합니다:

### 1. base.yaml
기본 인프라 리소스를 정의합니다:
- S3 버킷 (배포 및 출력용)
- Cognito User Pool 및 Identity Pool
- API Gateway
- SSM 파라미터 설정

### 2. frontend.yaml
프론트엔드 인프라를 정의합니다:
- S3 버킷 (프론트엔드 코드용)
- Amplify 애플리케이션 및 브랜치 설정
- 사용자 정의 도메인 설정 (선택적)

### 3. llm.yaml
LLM 서비스 인프라를 정의합니다:
- Lambda 함수 및 실행 역할
- API Gateway 리소스 및 메서드
- Lambda 권한 설정

### 4. main.yaml
다른 스택들을 조합하는 메인 스택으로, SSM 파라미터를 사용하여 스택 간 정보를 공유합니다.

## AWS 서비스 사용 상세 설명

### CloudFormation

모든 인프라 리소스가 CloudFormation 템플릿을 통해 정의되고 배포됩니다. 스택 간 종속성은 SSM 파라미터를 통해 관리됩니다. `main.yaml`은 다른 스택에서 생성된, SSM 파라미터에 저장된 값을 참조하여 각 리소스 간 통합을 제공합니다.

### Amazon Cognito

`base.yaml`에서 다음과 같은 Cognito 리소스를 생성합니다:
- **User Pool**: 사용자 인증 및 사용자 관리
- **User Pool Client**: 프론트엔드 애플리케이션과 인증 통합
- **Identity Pool**: AWS 리소스에 액세스할 수 있는 임시 자격 증명 제공
- **User Pool Domain**: 호스팅된 UI URL 제공

### AWS Amplify

`frontend.yaml`에서 Amplify 리소스를 설정하여 프론트엔드 호스팅을 제공합니다:
- **Amplify App**: 프론트엔드 애플리케이션 정의
- **Amplify Branch**: 환경별 브랜치 설정 (dev, test, prod)
- **빌드 설정**: 프론트엔드 빌드 프로세스 구성

### AWS Lambda

`llm.yaml`에서 Lambda 함수 및 관련 리소스를 설정합니다:
- **Lambda 함수**: LLM 추론을 위한 서버리스 함수
- **Lambda 레이어**: 공통 코드와 의존성을 관리하는 레이어
- **실행 역할**: Lambda 함수의 권한 정의

### Amazon API Gateway

`base.yaml`에서 API Gateway 인스턴스를 생성하고, `llm.yaml`에서 LLM 서비스에 대한 경로를 추가합니다:
- **REST API**: 백엔드 서비스용 API 엔드포인트
- **리소스 및 메서드**: /llm1, /llm2, /health 엔드포인트
- **CORS 설정**: 프론트엔드와의 통신을 위한 CORS 구성

### Amazon S3

여러 버킷을 사용하여 다양한 목적을 충족합니다:
- **배포 버킷**: Lambda 함수 및 레이어 패키지 저장
- **출력 버킷**: 애플리케이션 출력 저장
- **프론트엔드 버킷**: Amplify 애플리케이션 소스 코드 저장

### AWS Systems Manager Parameter Store

SSM Parameter Store를 사용하여 스택 간 정보를 공유하고 환경별 구성 값을 저장합니다:
- **스택 출력 저장**: 각 스택의 출력 값을 SSM 파라미터로 저장
- **스택 간 참조**: 다른 스택에서 SSM 파라미터를 참조하여 리소스 통합

### Amazon Bedrock

LLM 서비스에서 Amazon Bedrock API를 사용하여 AI21 Labs의 J2 모델을 활용한 자연어 처리 기능을 제공합니다:
- LLM 서비스는 사용자 질문을 SQL 쿼리로 변환
- 쿼리 결과를 자연어 설명으로 변환

## 배포 프로세스

### 사전 요구 사항

1. AWS CLI가 설치되어 있어야 합니다.
2. AWS 계정 자격 증명이 구성되어 있어야 합니다.
3. docker가 설치되어 있어야 합니다.
4. 배포할 환경에 대한 적절한 권한이 있어야 합니다.

### AWS CLI 설정

배포 전 AWS CLI가 올바르게 구성되어 있는지 확인하세요:

```bash
# AWS 자격 증명 구성
aws configure

# AWS Access Key ID 입력
# AWS Secret Access Key 입력
# 기본 리전 입력 (예: ap-northeast-2)
# 기본 출력 형식 입력 (json 권장)
```

현재 구성된 AWS 프로필 확인:

```bash
aws sts get-caller-identity
```

### 배포 스크립트 사용법

`deploy.sh` 스크립트는 전체 인프라를 자동으로 배포합니다. 다음과 같이 실행하세요:

```bash
# 개발 환경에 배포 (기본값)
./deploy.sh

# 특정 환경에 배포 (dev, test, prod)
./deploy.sh dev
./deploy.sh test
./deploy.sh prod
```

스크립트는 다음 단계를 자동으로 수행합니다:

1. **CloudFormation 버킷 준비**: 템플릿 파일을 저장할 S3 버킷을 생성하거나 확인
2. **기본 스택 배포**: 필수 인프라 리소스 생성 (S3, Cognito, API Gateway)
3. **프론트엔드 인프라 배포**: Amplify 애플리케이션 및 관련 리소스 생성
4. **레이어 및 Lambda 함수 패키징**: 코드 패키징 및 S3 업로드
5. **메인 스택 배포**: 다른 스택을 참조하여 전체 애플리케이션 통합
6. **환경 변수 설정**: 프론트엔드용 환경 변수 파일 생성
7. **프론트엔드 빌드 및 배포**: 프론트엔드 코드 빌드 및 Amplify에 배포

### 환경별 구성

각 환경(dev, test, prod)에 대해 다음과 같은 구성이 적용됩니다:

- **개발 환경(dev)**: 개발자 모드 활성화, 더 관대한 보안 설정
- **테스트 환경(test)**: 프로덕션과 유사하지만 개발 중인 기능 테스트 가능
- **프로덕션 환경(prod)**: 엄격한 보안 설정, 개발자 모드 비활성화

### 사용자 지정 도메인 설정 (선택 사항)

사용자 지정 도메인을 사용하려면 `deploy.sh` 스크립트에서 다음 변수를 수정하세요:

```bash
# 도메인 설정 (필요한 경우 수정)
DOMAIN_NAME="your-domain.com"  # 사용자 정의 도메인
CERTIFICATE_ARN="arn:aws:acm:region:account-id:certificate/certificate-id"  # ACM 인증서 ARN
```

## 배포 후 작업

배포가 완료되면 다음 정보가 출력됩니다:

- API Gateway URL
- Cognito User Pool 정보
- Amplify 애플리케이션 URL

이 정보를 사용하여 애플리케이션에 액세스하고 테스트할 수 있습니다.

## 프로젝트 확장

새로운 기능이나 서비스를 추가하려면:

1. `cloudformation/` 디렉토리에 새 템플릿 파일 추가
2. `services/` 디렉토리에 새 Lambda 함수 추가
3. `deploy.sh` 스크립트를 수정하여 새 리소스 배포 포함
4. `main.yaml`에 새 스택 참조 추가

## 문제 해결

### 배포 실패

배포가 실패하면 CloudFormation 콘솔에서 스택 이벤트를 확인하여 오류 메시지를 확인하세요. 일반적인 문제는 다음과 같습니다:

- **권한 부족**: 배포 사용자에게 필요한 권한이 없음
- **리소스 이름 충돌**: 이미 존재하는 리소스 이름 사용
- **서비스 한도**: AWS 서비스 한도 초과

### Lambda 오류

Lambda 함수 오류를 디버깅하려면:

- CloudWatch Logs에서 해당 Lambda 함수의 로그 확인
- 로컬에서 Lambda 함수 테스트 (AWS SAM 사용)

### API Gateway 문제

API 호출이 실패하면:

- API Gateway 콘솔에서 API 구성 확인
- CORS 설정 확인
- Lambda 통합 및 권한 확인

## 정리 (리소스 삭제)

프로젝트 리소스를 삭제하려면 AWS 콘솔에서 생성된 CloudFormation 스택을 삭제하세요:

1. 메인 스택 (`wga-{env}`) 삭제
2. 프론트엔드 스택 (`wga-frontend-{env}`) 삭제
3. 기본 스택 (`wga-base-{env}`) 삭제

일부 리소스(S3 버킷)는 DeletionPolicy가 'Retain'으로 설정되어 있어 수동으로 삭제해야 할 수 있습니다.
