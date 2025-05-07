FROM public.ecr.aws/lambda/python:3.11

WORKDIR /var/task

# 의존성 관련 파일 복사
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# 코드 복사
COPY awslabs/ awslabs/
COPY app.py ./app.py
COPY bootstrap ./bootstrap

RUN chmod +x /var/task/bootstrap

ENV PYTHONPATH=/var/task

ENTRYPOINT ["/var/task/bootstrap"]
