# WGA (WeGoAWS) - AWS 클라우드 운영 정보 챗봇 서비스

## 개요

WGA는 AWS 클라우드 운영 정보를 자연어로 질의응답할 수 있는 서버리스 기반의 AI 챗봇 서비스입니다. 사용자는 복잡한 AWS 콘솔을 직접 조작하는 대신, 간단한 자연어 질문을 통해 클라우드 자원 상태, 비용 분석, 보안 이벤트, 로그 분석 등의 정보를 즉시 얻을 수 있습니다.

### 핵심 가치
- **간편한 접근성**: 자연어 기반 질의로 AWS 전문 지식 없이도 클라우드 정보 조회 가능
- **실시간 모니터링**: CloudWatch, CloudTrail, GuardDuty 로그를 통한 실시간 시스템 상태 파악
- **비용 최적화**: AWS 비용 분석 및 최적화 제안
- **보안 강화**: 보안 이벤트 모니터링 및 알림

## 아키텍처

### 전체 시스템 아키텍처

![WGA 시스템 아키텍처](./images/architecture.png)

### 기술 스택
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Backend**: AWS Lambda (Python 3.12), API Gateway
- **AI/ML**: Claude 3.7 Sonnet, AWS Bedrock, MCP (Model Context Protocol)
- **Database**: DynamoDB
- **Storage**: S3 (정적 파일, 로그 저장)
- **Monitoring**: CloudWatch, CloudTrail, GuardDuty, Billing and Cost Management
- **Authentication**: AWS Cognito
- **Infrastructure**: CloudFormation, AWS CDK
- **CI/CD**: CodeBuild, Amplify

## 주요 기능

### 1. 자연어 기반 질의응답
- **로그 분석**: "어제 S3에 접근한 사용자는 누구인가요?"
- **비용 분석**: "지난 주 Opensearch 비용이 얼마나 나왔나요?"
- **보안 조회**: "최근 실패한 로그인 시도가 있나요?"
- **AWS 문서 검색**: "GuardDuty 심각도는 어떤 의미인가요?"

### 2. 실시간 모니터링 및 분석
- **CloudWatch 로그 분석**: 서비스별 로그 실시간 조회 및 분석
- **CloudTrail 이벤트**: AWS API 호출 이력 및 사용자 활동 추적
- **GuardDuty 보안 이벤트**: 보안 위협 감지 및 알림
- **비용 분석**: 서비스별, 리전별, 일별 비용 브레이크다운

### 3. 시각화 및 차트 생성
- **동적 차트**: 막대 차트, 라인 차트, 파이 차트, 산점도 등
- **아키텍처 다이어그램**: AWS 인프라 시각화
- **플로우차트**: 프로세스 흐름도 생성
- **마인드맵**: 구조화된 정보 표현

### 4. 다중 인터페이스 지원
- **웹 인터페이스**: React 기반 반응형 웹 앱
- **Slack 봇**: 슬랙 채널에서 직접 질의 가능

### 5. 대화 기록 관리
- **세션 관리**: 사용자별 대화 히스토리 저장
- **컨텍스트 유지**: 이전 대화 내용을 기반으로 한 연속 질의
- **히스토리 검색**: 과거 질의 및 답변 검색

## 프로젝트 구조

```
WGA_production/
├── frontend/                    # React 웹 애플리케이션
│   ├── src/
│   │   ├── components/         # 재사용 가능한 컴포넌트
│   │   ├── pages/             # 페이지 컴포넌트
│   │   ├── hooks/             # 커스텀 훅
│   │   ├── utils/             # 유틸리티 함수
│   │   └── types/             # TypeScript 타입 정의
│   ├── package.json
│   └── vite.config.ts
│
├── services/                    # Lambda 함수들
│   ├── llm/                    # LLM 서비스 (Claude, Bedrock)
│   │   ├── lambda_function.py
│   │   ├── llm_service.py
│   │   ├── mcp_client.py
│   │   ├── mcp_anthropic_client.py
│   │   └── mcp_bedrock_client.py
│   ├── db/                     # 데이터베이스 서비스
│   │   ├── lambda_function.py
│   │   └── enable_guardduty.py
│   ├── chat-history/           # 채팅 히스토리 관리
│   │   ├── lambda_function.py
│   │   └── chat_history_service.py
│   └── slackbot/              # Slack 봇 서비스
│       ├── lambda_function.py
│       └── slackbot_service.py
│
├── mcp/                        # Model Context Protocol 서버
│   ├── app.py                 # MCP 애플리케이션 메인
│   ├── lambda_mcp/            # MCP 서버 라이브러리
│   │   ├── lambda_mcp.py
│   │   ├── session.py
│   │   ├── mcp_types.py
│   │   ├── document_utils.py
│   │   ├── diagram_utils.py
│   │   └── chart_utils.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── layers/                     # Lambda 레이어
│   └── common/                # 공통 라이브러리
│       ├── config.py
│       ├── utils.py
│       ├── slackbot_session.py
│       └── requirements.txt
│
├── cloudformation/             # Infrastructure as Code
│   ├── base.yaml              # 기본 인프라 (Cognito, S3, DynamoDB)
│   ├── main.yaml              # 메인 스택
│   ├── llm.yaml               # LLM 서비스 스택
│   ├── frontend.yaml          # 프론트엔드 스택
│   ├── logs.yaml              # DB 관련 스택
│   ├── slackbot.yaml          # Slack 봇 스택
│   ├── chat-history.yaml      # 채팅 히스토리 스택
│   └── mcp.yaml               # MCP 서비스 스택
│
└── deploy.sh                  # 통합 배포 스크립트
```

## 설치 및 배포

### 사전 요구사항
- AWS CLI 설정 및 적절한 권한
- Node.js 18+ 
- Python 3.12+

### 환경 변수 설정
```bash
# AWS CLI 설정
aws configure
```

### 1단계: 기본 설정
```bash
# 프로젝트 클론
git clone https://github.com/WeGoAWS/WGA_production.git
cd WGA_production

# SSM 파라미터 설정 (필요한 경우)
aws ssm put-parameter --name "/wga/${Environment}/SlackbotToken" --value "your-slack-token" --type "SecureString"
aws ssm put-parameter --name "/wga/${Environment}/ANTHROPIC_API_KEY" --value "your-anthropic-key" --type "SecureString"
```

### 2단계: 통합 배포
```bash
# 개발 환경 배포
./deploy.sh dev

# 프로덕션 환경 배포
./deploy.sh prod
```

### 3단계: 배포 확인
배포 완료 후 다음 정보가 출력됩니다:
- **프론트엔드 URL**: `https://ENVIRONMENT.xxxxxxxxxxxxx.amplifyapp.com`
- **API Gateway URL**: `https://xxxxxxxxxx.execute-api.AWSREGION.amazonaws.com/ENVIRONMENT`
- **MCP Function URL**: `https://xxxxxxxxxx.lambda-url.AWSREGION.on.aws/`

## 설정 가이드

### Slack 봇 설정
1. Slack 앱 생성 및 봇 토큰 발급
2. SSM Parameter Store에 토큰 저장
3. Slack 앱에 다음 기능 추가:
   - Slash Commands: `/models`, `/req`
   - Interactive Components
   - Bot Token Scopes: `chat:write`, `im:write`

### AWS 권한 설정
Lambda 함수들이 다음 AWS 서비스에 접근할 수 있도록 IAM 권한 설정:
- CloudWatch Logs (읽기)
- CloudTrail (읽기)
- GuardDuty (읽기)
- Cost Explorer (읽기)
- Athena (실행)
- DynamoDB (읽기/쓰기)
- S3 (읽기/쓰기)
- Bedrock (호출)

## 사용 예시

### 웹 인터페이스
1. 브라우저에서 프론트엔드 URL 접속
2. Cognito를 통한 로그인
3. 채팅 인터페이스에서 자연어 질문 입력

### Slack 봇
```
# 모델 설정
/models

# 질의 실행
/req 어제 EC2 인스턴스를 시작한 사용자는 누구인가요?
/req 지난 주 S3 비용 분석해주세요
/req GuardDuty에서 감지된 보안 이벤트가 있나요?
```

## 주요 컴포넌트 상세

### LLM Service
- **Claude Sonnet 4**: 주요 언어 모델 (모델 변경 가능)
- **MCP Client**: Tool 호출 및 세션 관리
- **Multi-modal**: 텍스트, 차트, 다이어그램 생성

### MCP (Model Context Protocol) Server
- **AWS 도구들**: CloudWatch, CloudTrail, Cost Explorer API 래핑
- **문서 검색**: AWS 공식 문서 검색 및 추천
- **시각화**: 차트 및 다이어그램 생성
- **세션 관리**: DynamoDB 기반 상태 관리

### Database Service
- **테이블 관리**: CloudTrail, GuardDuty 로그 테이블 자동 생성
- **파티셔닝**: 날짜 기반 효율적인 데이터 조회

### Chat History Service
- **세션 관리**: 사용자별 대화 세션 관리
- **메시지 저장**: 질의/응답 히스토리 저장
- **컨텍스트 유지**: 이전 대화 기반 연속 질의 지원

## 보안 고려사항

### 인증 및 권한
- **AWS Cognito**: 사용자 인증 및 세션 관리
- **IAM 역할**: 최소 권한 원칙에 따른 Lambda 실행 역할
- **API Gateway**: 요청 검증 및 제한

### 데이터 보호
- **전송 중 암호화**: HTTPS/TLS
- **저장 중 암호화**: S3, DynamoDB 암호화
- **액세스 로깅**: CloudTrail을 통한 API 호출 추적

### 개인정보 보호
- **데이터 최소화**: 필요한 정보만 수집 및 저장
- **세션 만료**: 24시간 자동 세션 만료
- **로그 마스킹**: 민감한 정보 자동 마스킹

## 모니터링 및 운영

### 메트릭 및 알람
- **Lambda 함수**: 실행 시간, 오류율, 동시 실행 수
- **API Gateway**: 요청 수, 응답 시간, 오류율
- **비용**: 일일 비용 추이 및 예산 알람

### 로깅
- **CloudWatch Logs**: 모든 Lambda 함수 로그
- **X-Ray**: 분산 추적 및 성능 분석
- **구조화된 로깅**: JSON 형태의 로그 출력

### 백업 및 복구
- **S3**: 버전 관리 및 Cross-Region 복제
- **CloudFormation**: Infrastructure as Code를 통한 재배포

## 기여 가이드

### 개발 환경 설정
```bash
# 개발 종속성 설치
cd frontend && npm install
cd ../services/llm && pip install -r requirements.txt

# 로컬 개발 서버 실행
cd frontend && npm run dev

# Lambda 함수 로컬 테스트
cd services/llm && python lambda_function.py
```

## FAQ

### Q: 어떤 AWS 서비스를 지원하나요?
A: 현재 CloudWatch, CloudTrail, GuardDuty, Cost Explorer, EC2, S3, Lambda 등을 지원하며, 지속적으로 확장 중입니다.

### Q: 비용은 얼마나 발생하나요?
A: 사용량에 따라 다르지만, 일반적으로 월 $10-50 수준입니다. 주요 비용은 Lambda 실행, Bedrock API 호출, DynamoDB 사용량입니다.

### Q: 온프레미스에서도 사용할 수 있나요?
A: 현재는 AWS 클라우드 전용이지만, 향후 하이브리드 환경 지원을 계획하고 있습니다.

### Q: 다른 AI 모델을 사용할 수 있나요?
A: 네, Bedrock을 통해 다양한 모델을 지원하며, 설정에서 변경 가능합니다.

## 지원 및 문의

- **GitHub Issues**: [프로젝트 이슈 페이지](https://github.com/WeGoAWS/WGA_production/issues)

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.