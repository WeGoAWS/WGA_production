import json
import boto3
import requests
import time
from typing import Dict, Any, List, Optional


class MCPClient:
    """MCP(Model Context Protocol) Streamable HTTP 클라이언트 구현"""

    def __init__(self, mcp_url: str, auth_token: str = None, session_id: str = None):
        """
        MCP 클라이언트 초기화

        Args:
            mcp_url: MCP 서버 URL (Lambda Function URL 또는 Fargate 서비스 URL)
            auth_token: 인증 토큰 (선택 사항)
            session_id: 기존 세션 ID (선택 사항)
        """
        self.mcp_url = mcp_url.rstrip('/')
        self.session_id = session_id
        self.headers = {
            'Content-Type': 'application/json',
            'MCP-Version': '0.6'
        }

        # 인증 헤더 추가 (제공된 경우)
        if auth_token:
            self.headers['Authorization'] = f'Bearer {auth_token}'

    def initialize(self) -> str:
        """
        MCP 서버와 세션 초기화

        Returns:
            생성된 세션 ID
        """
        payload = {
            "jsonrpc": "2.0",
            "id": str(int(time.time() * 1000)),  # 타임스탬프 기반 ID 생성
            "method": "initialize"
        }

        response = requests.post(
            self.mcp_url,
            headers=self.headers,
            json=payload
        )

        if response.status_code != 200:
            raise Exception(f"MCP 초기화 실패: {response.status_code} - {response.text}")

        # 세션 ID 추출 및 저장
        self.session_id = response.headers.get('MCP-Session-Id')
        if not self.session_id:
            raise Exception("MCP 세션 ID를 받지 못했습니다")

        # 세션 ID를 가진 새 헤더 설정
        self.headers['MCP-Session-Id'] = self.session_id

        return self.session_id

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        사용 가능한 도구 목록 조회

        Returns:
            도구 목록
        """
        # 세션 ID가 없으면 초기화 필요
        if not self.session_id:
            self.initialize()

        payload = {
            "jsonrpc": "2.0",
            "id": str(int(time.time() * 1000)),
            "method": "tools/list"
        }

        response = requests.post(
            self.mcp_url,
            headers=self.headers,
            json=payload
        )

        if response.status_code != 200:
            raise Exception(f"도구 목록 조회 실패: {response.status_code} - {response.text}")

        result = response.json()
        if 'error' in result:
            raise Exception(f"도구 목록 조회 오류: {result['error']['message']}")

        return result.get('result', {}).get('tools', [])

    def call_tool(self, tool_name: str, tool_args: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        특정 도구 호출

        Args:
            tool_name: 호출할 도구 이름
            tool_args: 도구에 전달할 인자 (선택 사항)

        Returns:
            도구 실행 결과
        """
        # 세션 ID가 없으면 초기화 필요
        if not self.session_id:
            self.initialize()

        payload = {
            "jsonrpc": "2.0",
            "id": str(int(time.time() * 1000)),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_args or {}
            }
        }

        response = requests.post(
            self.mcp_url,
            headers=self.headers,
            json=payload
        )

        if response.status_code != 200:
            raise Exception(f"도구 호출 실패: {response.status_code} - {response.text}")

        result = response.json()
        if 'error' in result:
            raise Exception(f"도구 호출 오류: {result['error']['message']}")

        return result.get('result', {})

    def close(self) -> bool:
        """
        MCP 세션 종료

        Returns:
            성공 여부
        """
        if not self.session_id:
            return True  # 세션이 없으면 이미 종료된 것으로 간주

        response = requests.delete(
            self.mcp_url,
            headers=self.headers
        )

        # 세션 ID 초기화
        self.session_id = None
        if 'MCP-Session-Id' in self.headers:
            del self.headers['MCP-Session-Id']

        return response.status_code == 204  # 세션 삭제 성공은 204 No Content