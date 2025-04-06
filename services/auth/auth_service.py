# services/auth/auth_service.py
import json
import time
import urllib.request
import boto3
from jose import jwk, jwt
from jose.utils import base64url_decode
from common.db import *
from common.config import CONFIG

def verify_cognito_token(id_token, cognito_client_id, user_pool_id, region):
    """
    Cognito JWT 토큰의 유효성을 검증합니다.
    
    Args:
        id_token (str): 검증할 Cognito ID 토큰
        cognito_client_id (str): Cognito 앱 클라이언트 ID
        user_pool_id (str): Cognito 사용자 풀 ID
        region (str): AWS 리전
        
    Returns:
        tuple: (is_valid, claims, error_msg)
            - is_valid (bool): 토큰 유효성 여부
            - claims (dict): 검증된 경우 토큰의 클레임 정보
            - error_msg (str): 오류 메시지 (유효한 경우 None)
    """
    # JWT 토큰 검증을 위한 공개키 가져오기
    keys_url = f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json'
    
    try:
        with urllib.request.urlopen(keys_url) as f:
            response = f.read()
        keys = json.loads(response.decode('utf-8'))['keys']
    except Exception as e:
        return False, None, f'Failed to fetch JWKS: {str(e)}'
    
    # JWT 토큰 헤더 디코딩
    try:
        headers = jwt.get_unverified_headers(id_token)
        kid = headers['kid']
    except Exception as e:
        return False, None, f'Invalid JWT headers: {str(e)}'
    
    # 검증할 키 찾기
    key_index = -1
    for i in range(len(keys)):
        if kid == keys[i]['kid']:
            key_index = i
            break
    
    if key_index == -1:
        return False, None, 'Public key not found in jwks.json'
    
    # 공개키 가져오기
    try:
        public_key = jwk.construct(keys[key_index])
    except Exception as e:
        return False, None, f'Failed to construct public key: {str(e)}'
    
    # 토큰 서명 검증
    try:
        message, encoded_signature = id_token.rsplit('.', 1)
        decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))
        
        # 서명 검증 수행
        is_verified = public_key.verify(message.encode("utf8"), decoded_signature)
        
        if not is_verified:
            return False, None, 'Signature verification failed'
    except Exception as e:
        return False, None, f'Signature verification error: {str(e)}'
    
    # 클레임 검증
    try:
        claims = jwt.get_unverified_claims(id_token)
        
        # 만료 시간 확인
        current_time = time.time()
        expiration_time = claims['exp']
        
        if current_time > expiration_time:
            return False, None, 'Token is expired'
        
        # 발행자 확인
        expected_issuer = f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}'
        actual_issuer = claims['iss']
        
        if actual_issuer != expected_issuer:
            return False, None, 'Token was not issued by expected provider'
        
        # 클라이언트 ID 확인
        if claims['aud'] != cognito_client_id and claims.get('client_id') != cognito_client_id:
            return False, None, 'Token was not issued for this client'
        
        return True, claims, None
    except KeyError as e:
        return False, None, f'Missing required claim: {str(e)}'
    except Exception as e:
        return False, None, f'Error validating claims: {str(e)}'

def create_user_session(id_token, access_token, refresh_token, provider, claims):
    """
    사용자의 새 세션을 생성하고 사용자 정보를 저장합니다.
    
    Args:
        id_token (str): ID 토큰
        access_token (str): 액세스 토큰 (선택적)
        refresh_token (str): 리프레시 토큰 (선택적)
        provider (str): 인증 제공자 (cognito, google, azure)
        claims (dict): 토큰 클레임 정보
        
    Returns:
        str: 생성된 세션 ID
    """
    # 사용자 정보 저장
    user_data = {
        "sub": claims.get("sub"),
        "email": claims.get("email"),
        "issuer": claims.get("iss"),
        "provider": provider,
        "last_login": int(time.time())
    }
    
    create_or_update_user(user_data)
    
    # 세션 데이터 구성
    session_data = {
        'id_token': id_token,
        'provider': provider,
        'user_sub': claims.get('sub'),
        'expiration': int(claims.get('exp')),
        'created_at': int(time.time())
    }
    
    # 추가 토큰이 있는 경우 세션에 저장
    if access_token:
        session_data['access_token'] = access_token
    
    if refresh_token:
        session_data['refresh_token'] = refresh_token
    
    # 세션 생성
    session_id = create_session(session_data)
    return session_id

def logout_user(session_id):
    """
    사용자 로그아웃 처리 - 세션 삭제
    
    Args:
        session_id (str): 삭제할 세션 ID
        
    Returns:
        bool: 성공 여부
    """
    return delete_session(session_id)

def refresh_tokens(refresh_token, provider):
    """
    리프레시 토큰을 사용하여 새 액세스 토큰 발급
    
    Args:
        refresh_token (str): 리프레시 토큰
        provider (str): 인증 제공자
        
    Returns:
        dict: 새 토큰 정보 또는 None (실패 시)
    """
    if provider == "cognito":
        client = boto3.client('cognito-idp', region_name=CONFIG['aws_region'])
        
        try:
            response = client.initiate_auth(
                ClientId=CONFIG['cognito']['client_id'],
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token
                }
            )
            
            auth_result = response.get('AuthenticationResult', {})
            return {
                'id_token': auth_result.get('IdToken'),
                'access_token': auth_result.get('AccessToken'),
                'expires_in': auth_result.get('ExpiresIn')
            }
        except Exception as e:
            print(f"Error refreshing tokens: {e}")
            return None
    
    # 다른 제공자 구현 추가 가능
    return None
    
def get_session_info(session_id):
    """
    세션 ID로 세션 정보를 조회하는 래퍼 함수
    
    Args:
        session_id (str): 세션 ID
        
    Returns:
        dict: 세션 정보 또는 None
    """
    return get_session(session_id)

def validate_and_create_session(provider, id_token, access_token=None, refresh_token=None):
    """
    토큰 검증 및 세션 생성을 처리하는 통합 함수
    
    Args:
        provider (str): 인증 제공자 (cognito, google, azure)
        id_token (str): ID 토큰
        access_token (str, optional): 액세스 토큰
        refresh_token (str, optional): 리프레시 토큰
        
    Returns:
        tuple: (success, session_id, claims, error_message)
            - success (bool): 성공 여부
            - session_id (str): 생성된 세션 ID 또는 None
            - claims (dict): 토큰 클레임 정보 또는 None
            - error_message (str): 오류 메시지 또는 None
    """
    
    # 토큰 검증
    if provider == "cognito":
        region = CONFIG['aws_region']
        user_pool_id = CONFIG['cognito']['user_pool_id']
        client_id = CONFIG['cognito']['client_id']
        
        is_valid, claims, error_msg = verify_cognito_token(
            id_token, client_id, user_pool_id, region
        )
        
        if not is_valid:
            return False, None, None, error_msg
        
        # 세션 생성
        session_id = create_user_session(
            id_token, access_token, refresh_token, provider, claims
        )
        
        return True, session_id, claims, None
    
    # 다른 제공자 지원 추가 가능
    return False, None, None, "Unsupported provider"