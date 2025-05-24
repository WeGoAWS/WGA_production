# 공식 AWS Lambda Python 기본 이미지를 사용합니다
FROM public.ecr.aws/lambda/python:3.12

# 컨테이너 내 작업 디렉토리 설정
WORKDIR ${LAMBDA_TASK_ROOT}

# 시스템 의존성을 먼저 설치 (Amazon Linux 2023에서 dnf 사용)
RUN dnf update -y && \
    dnf install -y \
        graphviz \
        graphviz-devel \
        gcc \
        gcc-c++ \
        make \
        pkgconfig \
    && dnf clean all

# Docker 캐시를 활용하기 위해 먼저 요구 사항을 복사합니다
COPY requirements.txt .

# Python 종속성 설치
RUN pip install --no-cache-dir -r requirements.txt

# lambda_mcp 모듈 폴더 복사
COPY lambda_mcp/ lambda_mcp/

# 애플리케이션 코드의 나머지를 복사합니다
COPY app.py .

# 핸들러 함수 실행 명령 설정
CMD ["app.lambda_handler"]