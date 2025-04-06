# layers/common/db.py
import boto3
import time
import uuid
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import logging

# 로깅 설정
logger = logging.getLogger("wga-db")
logger.setLevel(logging.INFO)

# CONFIG 불러오기
from common.config import CONFIG

class DynamoDBManager:
    """
    DynamoDB 테이블 관리를 위한 제네릭 클래스
    여러 테이블에 대한 CRUD 작업을 중앙화하고 중복 코드를 제거
    """
    
    def __init__(self, region_name=None):
        """
        DynamoDB 리소스 및 클라이언트 초기화
        
        Args:
            region_name (str, optional): AWS 리전. 기본값은 CONFIG에서 가져옴
        """
        self.region_name = region_name or CONFIG['aws_region']
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region_name)
        self.dynamodb_client = boto3.client('dynamodb', region_name=self.region_name)
        
        # 테이블 객체 캐시
        self._table_cache = {}
        
        # 테이블 초기화
        self._initialize_tables()
    
    def _initialize_tables(self):
        """테이블 객체 초기화"""
        # 주요 테이블들
        self.tables = {
            'sessions': CONFIG['tables']['sessions'],
            'users': CONFIG['tables']['users'],
            'analysis_results': CONFIG['tables']['analysis_results'],
            'user_behavior_profiles': CONFIG['tables']['user_behavior_profiles'],
            'role_templates': CONFIG['tables']['role_templates'],
            'role_history': CONFIG['tables']['role_history'],
            'anomaly_events': CONFIG['tables']['anomaly_events'],
            'access_decisions': CONFIG['tables']['access_decisions']
        }
    
    def _get_table(self, table_name):
        """
        테이블 객체 가져오기 (캐싱 적용)
        
        Args:
            table_name (str): 테이블 이름
            
        Returns:
            Table: DynamoDB 테이블 객체
        """
        if table_name not in self._table_cache:
            self._table_cache[table_name] = self.dynamodb.Table(table_name)
        return self._table_cache[table_name]
    
    # 제네릭 CRUD 함수들
    
    def get_item(self, table_name, key_dict):
        """
        항목 조회
        
        Args:
            table_name (str): 테이블 이름
            key_dict (dict): 키 값 사전
            
        Returns:
            dict: 조회된 항목 또는 None
        """
        try:
            table = self._get_table(table_name)
            response = table.get_item(Key=key_dict)
            return response.get('Item')
        except ClientError as e:
            logger.error(f"Error retrieving item from {table_name}: {e.response['Error']['Message']}")
            return None
    
    def put_item(self, table_name, item_dict):
        """
        항목 생성 또는 업데이트
        
        Args:
            table_name (str): 테이블 이름
            item_dict (dict): 항목 데이터
            
        Returns:
            bool: 성공 여부
        """
        try:
            table = self._get_table(table_name)
            table.put_item(Item=item_dict)
            return True
        except ClientError as e:
            logger.error(f"Error putting item to {table_name}: {e.response['Error']['Message']}")
            return False
    
    def update_item(self, table_name, key_dict, update_expression, expression_attributes):
        """
        항목 부분 업데이트
        
        Args:
            table_name (str): 테이블 이름
            key_dict (dict): 키 값 사전
            update_expression (str): 업데이트 표현식
            expression_attributes (dict): 표현식 속성 값
            
        Returns:
            bool: 성공 여부
        """
        try:
            table = self._get_table(table_name)
            table.update_item(
                Key=key_dict,
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attributes
            )
            return True
        except ClientError as e:
            logger.error(f"Error updating item in {table_name}: {e.response['Error']['Message']}")
            return False
    
    def delete_item(self, table_name, key_dict):
        """
        항목 삭제
        
        Args:
            table_name (str): 테이블 이름
            key_dict (dict): 키 값 사전
            
        Returns:
            bool: 성공 여부
        """
        try:
            table = self._get_table(table_name)
            table.delete_item(Key=key_dict)
            return True
        except ClientError as e:
            logger.error(f"Error deleting item from {table_name}: {e.response['Error']['Message']}")
            return False
    
    def query_items(self, table_name, key_condition_expression, index_name=None, filter_expression=None, 
                   limit=None, scan_index_forward=True, exclusive_start_key=None):
        """
        항목 쿼리
        
        Args:
            table_name (str): 테이블 이름
            key_condition_expression: 키 조건 표현식
            index_name (str, optional): 인덱스 이름
            filter_expression: 필터 표현식
            limit (int, optional): 최대 결과 수
            scan_index_forward (bool): 정렬 방향
            exclusive_start_key (dict, optional): 페이지네이션 시작 키
            
        Returns:
            dict: 쿼리 결과
        """
        try:
            table = self._get_table(table_name)
            params = {
                'KeyConditionExpression': key_condition_expression,
                'ScanIndexForward': scan_index_forward
            }
            
            if index_name:
                params['IndexName'] = index_name
            
            if filter_expression:
                params['FilterExpression'] = filter_expression
            
            if limit:
                params['Limit'] = limit
            
            if exclusive_start_key:
                params['ExclusiveStartKey'] = exclusive_start_key
            
            return table.query(**params)
        except ClientError as e:
            logger.error(f"Error querying items from {table_name}: {e.response['Error']['Message']}")
            return {'Items': []}
    
    def scan_items(self, table_name, filter_expression=None, limit=None, exclusive_start_key=None):
        """
        테이블 스캔
        
        Args:
            table_name (str): 테이블 이름
            filter_expression: 필터 표현식
            limit (int, optional): 최대 결과 수
            exclusive_start_key (dict, optional): 페이지네이션 시작 키
            
        Returns:
            dict: 스캔 결과
        """
        try:
            table = self._get_table(table_name)
            params = {}
            
            if filter_expression:
                params['FilterExpression'] = filter_expression
            
            if limit:
                params['Limit'] = limit
            
            if exclusive_start_key:
                params['ExclusiveStartKey'] = exclusive_start_key
            
            return table.scan(**params)
        except ClientError as e:
            logger.error(f"Error scanning items from {table_name}: {e.response['Error']['Message']}")
            return {'Items': []}

# 싱글톤 인스턴스
db_manager = DynamoDBManager()

# 세션 관련 함수
def get_session(session_id):
    """
    세션 ID로 세션 정보 조회
    
    Args:
        session_id (str): 세션 ID
        
    Returns:
        dict: 세션 정보 또는 None
    """
    if not session_id:
        return None
    
    session = db_manager.get_item(db_manager.tables['sessions'], {'session_id': session_id})
    
    # 세션 만료 확인
    if session and session.get('expiration', 0) < int(time.time()):
        # 만료된 세션 삭제
        db_manager.delete_item(db_manager.tables['sessions'], {'session_id': session_id})
        return None
    
    return session

def create_session(session_data):
    """
    새 세션 생성
    
    Args:
        session_data (dict): 세션 데이터
        
    Returns:
        str: 생성된 세션 ID 또는 None
    """
    if not session_data.get('session_id'):
        session_data['session_id'] = str(uuid.uuid4())
    
    if not session_data.get('created_at'):
        session_data['created_at'] = int(time.time())
    
    if db_manager.put_item(db_manager.tables['sessions'], session_data):
        return session_data['session_id']
    return None

def delete_session(session_id):
    """
    세션 삭제
    
    Args:
        session_id (str): 세션 ID
        
    Returns:
        bool: 성공 여부
    """
    return db_manager.delete_item(db_manager.tables['sessions'], {'session_id': session_id})

# 사용자 관련 함수
def get_user(sub):
    """
    사용자 정보 조회
    
    Args:
        sub (str): 사용자 ID (Cognito sub)
        
    Returns:
        dict: 사용자 정보 또는 None
    """
    return db_manager.get_item(db_manager.tables['users'], {'sub': sub})

def create_or_update_user(user_data):
    """
    사용자 정보 생성 또는 업데이트
    
    Args:
        user_data (dict): 사용자 데이터
        
    Returns:
        bool: 성공 여부
    """
    sub = user_data.get('sub')
    if not sub:
        logger.error("사용자 ID(sub)가 누락되었습니다.")
        return False
    
    # 기존 사용자 확인
    existing_user = get_user(sub)
    
    if not existing_user:
        # 신규 사용자 생성
        if not user_data.get('last_login'):
            user_data['last_login'] = int(time.time())
        return db_manager.put_item(db_manager.tables['users'], user_data)
    else:
        # 기존 사용자 업데이트
        update_expr = "set "
        expr_values = {}
        
        for key, value in user_data.items():
            if key != 'sub':  # 기본 키는 업데이트할 수 없음
                update_expr += f"{key}=:{key}, "
                expr_values[f":{key}"] = value
        
        # 마지막 쉼표 제거
        update_expr = update_expr.rstrip(", ")
        
        return db_manager.update_item(
            db_manager.tables['users'],
            {'sub': sub},
            update_expr,
            expr_values
        )

# 분석 결과 관련 함수
def create_analysis_result(result_data):
    """
    분석 결과 생성
    
    Args:
        result_data (dict): 분석 결과 데이터
        
    Returns:
        str: 생성된 결과 ID 또는 None
    """
    if not result_data.get('id'):
        result_data['id'] = str(uuid.uuid4())
    
    if not result_data.get('created_at'):
        result_data['created_at'] = int(time.time())
    
    if db_manager.put_item(db_manager.tables['analysis_results'], result_data):
        return result_data['id']
    return None

def get_analysis_result(result_id):
    """
    분석 결과 조회
    
    Args:
        result_id (str): 결과 ID
        
    Returns:
        dict: 분석 결과 또는 None
    """
    return db_manager.get_item(db_manager.tables['analysis_results'], {'id': result_id})

def get_user_analysis_results(user_arn, limit=20):
    """
    사용자별 분석 결과 조회
    
    Args:
        user_arn (str): 사용자 ARN
        limit (int): 최대 결과 수
        
    Returns:
        list: 분석 결과 목록
    """
    response = db_manager.query_items(
        db_manager.tables['analysis_results'],
        Key('user_arn').eq(user_arn),
        index_name='UserArnIndex',
        limit=limit,
        scan_index_forward=False  # 내림차순 (최신순)
    )
    return response.get('Items', [])

def get_latest_analysis_results(limit=20):
    """
    최신 분석 결과 조회
    
    Args:
        limit (int): 최대 결과 수
        
    Returns:
        list: 분석 결과 목록
    """
    # GSI가 없으므로 스캔 후 정렬
    response = db_manager.scan_items(
        db_manager.tables['analysis_results'],
        limit=limit * 2  # 충분히 많이 가져온 후 정렬
    )
    
    items = response.get('Items', [])
    items.sort(key=lambda x: x.get('created_at', 0), reverse=True)
    
    return items[:limit]

# 이상 행동 이벤트 관련 함수
def save_anomaly_event(event_data):
    """
    이상 행동 이벤트 저장
    
    Args:
        event_data (dict): 이벤트 데이터
        
    Returns:
        str: 생성된 이벤트 ID 또는 None
    """
    if not event_data.get('id'):
        event_data['id'] = str(uuid.uuid4())
    
    if not event_data.get('timestamp'):
        event_data['timestamp'] = int(time.time())
    
    if db_manager.put_item(db_manager.tables['anomaly_events'], event_data):
        return event_data['id']
    return None

def get_anomaly_events_by_user(user_arn, limit=20):
    """
    사용자별 이상 행동 이벤트 조회
    
    Args:
        user_arn (str): 사용자 ARN
        limit (int): 최대 결과 수
        
    Returns:
        list: 이상 행동 이벤트 목록
    """
    response = db_manager.query_items(
        db_manager.tables['anomaly_events'],
        Key('user_arn').eq(user_arn),
        index_name='UserArnIndex',
        limit=limit,
        scan_index_forward=False  # 내림차순 (최신순)
    )
    return response.get('Items', [])

# 사용자 행동 프로파일 관련 함수
def get_user_activity_profile(user_arn):
    """
    사용자 행동 프로파일 조회
    
    Args:
        user_arn (str): 사용자 ARN
        
    Returns:
        dict: 사용자 행동 프로파일 또는 None
    """
    return db_manager.get_item(db_manager.tables['user_behavior_profiles'], {'user_arn': user_arn})

def update_user_activity_profile(user_arn, profile_data):
    """
    사용자 행동 프로파일 업데이트
    
    Args:
        user_arn (str): 사용자 ARN
        profile_data (dict): 프로파일 데이터
        
    Returns:
        bool: 성공 여부
    """
    profile_data['user_arn'] = user_arn
    if not profile_data.get('updated_at'):
        profile_data['updated_at'] = int(time.time())
    
    return db_manager.put_item(db_manager.tables['user_behavior_profiles'], profile_data)

# 역할 템플릿 관련 함수
def get_role_template(template_id):
    """
    역할 템플릿 조회
    
    Args:
        template_id (str): 템플릿 ID
        
    Returns:
        dict: 역할 템플릿 또는 None
    """
    return db_manager.get_item(db_manager.tables['role_templates'], {'id': template_id})

# 역할 이력 관련 함수
def save_role_history(history_data):
    """
    역할 변경 이력 저장
    
    Args:
        history_data (dict): 이력 데이터
        
    Returns:
        str: 생성된 이력 ID 또는 None
    """
    if not history_data.get('id'):
        history_data['id'] = str(uuid.uuid4())
    
    if not history_data.get('timestamp'):
        history_data['timestamp'] = int(time.time())
    
    if db_manager.put_item(db_manager.tables['role_history'], history_data):
        return history_data.get('id')
    return None

# 접근 결정 관련 함수
def save_access_decision(decision_data):
    """
    접근 결정 이력 저장
    
    Args:
        decision_data (dict): 결정 데이터
        
    Returns:
        str: 생성된 결정 ID 또는 None
    """
    # request_id가 없으면 생성
    if not decision_data.get('request_id'):
        decision_data['request_id'] = str(uuid.uuid4())
    
    # 타임스탬프가 없으면 현재 시간 사용
    if not decision_data.get('timestamp'):
        decision_data['timestamp'] = int(time.time())
    
    if db_manager.put_item(db_manager.tables['access_decisions'], decision_data):
        return decision_data.get('request_id')
    return None

# 테이블 존재 여부 확인 및 생성 함수는 별도 모듈로 분리하여 배포 스크립트에서 사용하는 것이 좋음