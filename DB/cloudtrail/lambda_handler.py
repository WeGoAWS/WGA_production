import boto3
import json
import re
import time
import dotenv
import os
import logging
from datetime import datetime, timedelta
#환경설정
dotenv.load_dotenv()
athena = boto3.client('athena')
s3 = boto3.client('s3')
DATABASE = os.getenv('ATHENA_DATABASE')
TABLE = os.getenv('ATHENA_TABLE')
BUCKET = os.getenv('S3_BUCKET')
REGION = os.getenv('AWS_REGION')

def create_table(s3_path):
    # 테이블이 존재하지 않을 경우 생성함
    s3
