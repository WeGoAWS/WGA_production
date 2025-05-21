import json
import time
import boto3
from typing import Dict, Any, List, Optional
from mcp_client import MCPClient


class BedrockMCPClient:
    """Bedrock과 통합된 MCP 클라이언트"""

    def __init__(self, mcp_url: str, region: str = None, auth_token: str = None, model_id: str = None,
                 session_id: str = None, max_retries: int = 5, max_iterations: int = 10):
        """
        Bedrock MCP 클라이언트 초기화

        Args:
            mcp_url: MCP 서버 URL
            region: AWS 리전 (기본값: Lambda 함수의 리전)
            auth_token: MCP 인증 토큰 (선택 사항)
            model_id: Bedrock 모델 ID (기본값: 'anthropic.claude-3-haiku-20240307-v1:0')
            session_id: 기존 세션 ID (선택 사항)
            max_retries: 작업 상태 확인을 위한 최대 재시도 횟수
            max_iterations: 도구 호출을 위한 최대 반복 횟수
        """
        self.mcp_client = MCPClient(mcp_url, auth_token, session_id)
        self.region = region or boto3.session.Session().region_name
        self.model_id = model_id or 'anthropic.claude-3-haiku-20240307-v1:0'
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=self.region)
        self.tools = []
        self.messages = []
        self.max_retries = max_retries
        self.max_iterations = max_iterations
        self.pending_tasks = {}  # 대기 중인 작업 ID 및 상태 추적

    def initialize(self) -> str:
        """
        MCP 세션 초기화 및 도구 목록 로드

        Returns:
            세션 ID
        """
        session_id = self.mcp_client.initialize()
        self.tools = self.mcp_client.list_tools()
        return session_id

    def _check_task_completion(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        응답에서 대기 중인 작업을 확인하고 완료될 때까지 대기

        Args:
            response: Bedrock 모델 응답

        Returns:
            최종 응답
        """
        # 응답에서 텍스트 추출
        output_message = response.get('output', {}).get('message', {})
        content = output_message.get('content', [])

        # 응답 텍스트 확인
        response_text = ""
        for item in content:
            if 'text' in item:
                response_text += item['text']

        # 작업 ID 패턴 탐지
        import re
        task_patterns = [
            r'task[_\s]id["\s:]+([a-zA-Z0-9_-]+)',  # task_id: "abc123"
            r'execution[_\s]arn["\s:]+([a-zA-Z0-9:/_-]+)',  # execution_arn: "arn:aws:..."
            r'status["\s:]+pending',  # status: "pending"
            r'status["\s:]+in[_\s]progress'  # status: "in_progress"
        ]

        pending_task_detected = False
        task_ids = []

        # 작업 ID 추출 및 실행 ARN 검색
        for pattern in task_patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            if matches:
                pending_task_detected = True
                task_ids.extend(matches)

        # 대기 중인 작업이 감지되지 않은 경우 현재 응답 반환
        if not pending_task_detected or not task_ids:
            return response

        # 대기 중인 작업 처리
        for task_id in task_ids:
            if not task_id in self.pending_tasks:
                self.pending_tasks[task_id] = {
                    'id': task_id,
                    'start_time': time.time(),
                    'status': 'pending'
                }

        # 작업 완료 확인 도구 이름 추출
        check_status_tools = []
        status_tool_pattern = r'check[_\s].*?status[_\s]tool["\s:]+([a-zA-Z0-9_-]+)'
        status_matches = re.findall(status_tool_pattern, response_text, re.IGNORECASE)

        if status_matches:
            check_status_tools.extend(status_matches)
        else:
            # 기본 상태 확인 도구 사용
            check_status_tools = ["check-log-analysis-status", "get-analysis-status", "check-task-status"]

        # 모든 대기 중인 작업에 대해 상태 확인
        for task_id, task_info in list(self.pending_tasks.items()):
            if task_info['status'] in ['complete', 'error']:
                continue

            for retry in range(self.max_retries):
                # 작업 상태 확인
                status_checked = False

                for tool_name in check_status_tools:
                    try:
                        # 도구 이름을 MCP 형식으로 변환 (언더스코어를 대시로)
                        mcp_tool_name = tool_name.replace('_', '-')

                        # 작업 ID가 ARN인지 확인
                        if "arn:aws" in task_id:
                            status_result = self.mcp_client.call_tool(mcp_tool_name, {"execution_arn": task_id})
                        else:
                            status_result = self.mcp_client.call_tool(mcp_tool_name, {"task_id": task_id})

                        status_checked = True

                        # 작업 상태 확인
                        if status_result.get('status') == 'complete':
                            self.pending_tasks[task_id]['status'] = 'complete'
                            self.pending_tasks[task_id]['result'] = status_result
                            break
                        elif status_result.get('status') == 'error':
                            self.pending_tasks[task_id]['status'] = 'error'
                            self.pending_tasks[task_id]['error'] = status_result.get('message')
                            break

                        # 여전히 진행 중인 경우 대기
                        time.sleep(2)

                    except Exception as e:
                        # 이 도구가 실패하면 다음 도구로 시도
                        continue

                # 하나 이상의 도구로 상태를 확인했고 작업이 완료된 경우
                if status_checked and self.pending_tasks[task_id]['status'] in ['complete', 'error']:
                    break

                # 타임아웃 확인 (60초)
                if time.time() - task_info['start_time'] > 60:
                    self.pending_tasks[task_id]['status'] = 'timeout'
                    break

                # 잠시 대기 후 다시 시도
                time.sleep(2)

        # 모든 작업이 완료되었는지 확인
        all_tasks_completed = all(task['status'] in ['complete', 'error', 'timeout']
                                  for task in self.pending_tasks.values())

        if all_tasks_completed:
            # 작업 결과를 포함하여 최종 분석 요청
            task_results = {task_id: task_info.get('result', {})
                            for task_id, task_info in self.pending_tasks.items()
                            if task_info['status'] == 'complete'}

            task_errors = {task_id: task_info.get('error', "Unknown error")
                           for task_id, task_info in self.pending_tasks.items()
                           if task_info['status'] in ['error', 'timeout']}

            # 최종 분석 요청 메시지 구성
            final_request = "모든 비동기 작업이 완료되었습니다. 다음 결과를 바탕으로 최종 분석을 제공해주세요:\n\n"

            if task_results:
                final_request += "## 완료된 작업 결과\n"
                for task_id, result in task_results.items():
                    final_request += f"작업 ID: {task_id}\n"
                    final_request += f"결과: {json.dumps(result, ensure_ascii=False)[:500]}...\n\n"

            if task_errors:
                final_request += "## 오류가 발생한 작업\n"
                for task_id, error in task_errors.items():
                    final_request += f"작업 ID: {task_id}, 오류: {error}\n"

            # 최종 분석 요청
            self.messages.append({
                'role': 'user',
                'content': [{'text': final_request}]
            })

            final_response = self.bedrock_client.converse(
                modelId=self.model_id,
                messages=self.messages
            )

            # 메시지에 최종 응답 추가
            final_message = final_response.get('output', {}).get('message', {})
            self.messages.append(final_message)

            # 대기 중인 작업 목록 초기화
            self.pending_tasks = {}

            return final_response
        else:
            # 상태 업데이트 요청
            status_summary = "일부 작업이 아직 진행 중입니다. 현재 상태:\n\n"
            for task_id, task_info in self.pending_tasks.items():
                status_summary += f"작업 ID: {task_id}, 상태: {task_info['status']}\n"

            self.messages.append({
                'role': 'user',
                'content': [{'text': status_summary + "\n계속해서 작업 상태를 확인해주세요."}]
            })

            # 업데이트된 상태로 모델 다시 호출 (toolConfig 포함)
            updated_request_config = {
                'modelId': self.model_id,
                'messages': self.messages,
                'toolConfig': {
                    'tools': self.bedrock_tools,
                    'toolChoice': {'auto': {}}
                }
            }

            # 시스템 프롬프트가 있는 경우 추가
            if hasattr(self, 'system_prompt') and self.system_prompt:
                updated_request_config['system'] = [{'text': self.system_prompt}]

            updated_response = self.bedrock_client.converse(**updated_request_config)

            # 메시지에 업데이트된 응답 추가
            updated_message = updated_response.get('output', {}).get('message', {})
            self.messages.append(updated_message)

            # 재귀적으로 작업 완료 확인
            return self._check_task_completion(updated_response)

    def invoke_with_tools(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        """
        MCP 도구를 사용하여 Bedrock 모델 호출

        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택 사항)

        Returns:
            Bedrock 모델 응답
        """
        # 세션 및 도구가 초기화되지 않은 경우
        if not self.tools:
            self.initialize()

        # 시스템 프롬프트 저장 (나중에 재사용)
        if system_prompt:
            self.system_prompt = system_prompt

        # 메시지 추가
        self.messages.append({
            'role': 'user',
            'content': [{'text': prompt}]
        })

        # Bedrock 도구 형식으로 변환
        self.bedrock_tools = []
        for tool in self.tools:
            self.bedrock_tools.append({
                'toolSpec': {
                    'name': tool['name'].replace('-', '_'),  # 대시를 언더스코어로 변환 (Bedrock 요구사항)
                    'description': tool['description'],
                    'inputSchema': {
                        'json': {
                            'type': tool['inputSchema'].get('type', 'object'),
                            'properties': tool['inputSchema'].get('properties', {}),
                            'required': tool['inputSchema'].get('required', [])
                        }
                    }
                }
            })

        # Bedrock 요청 구성
        request = {
            'modelId': self.model_id,
            'messages': self.messages,
            'toolConfig': {
                'tools': self.bedrock_tools,
                'toolChoice': {'auto': {}}
            }
        }

        # 시스템 프롬프트가 제공된 경우 추가
        if system_prompt:
            request['system'] = [{'text': system_prompt}]

        # 모델 호출 루프 시작 (도구 사용이 완료될 때까지)
        final_response = None
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # Bedrock 모델 호출
            response = self.bedrock_client.converse(**request)

            # 응답 파싱
            stop_reason = response.get('stopReason')
            output_message = response.get('output', {}).get('message', {})

            # 메시지에 응답 추가
            if output_message:
                self.messages.append(output_message)

            # 도구 사용 요청인 경우
            if stop_reason == 'tool_use':
                # 도구 사용 블록 추출
                tool_uses = []
                for item in output_message.get('content', []):
                    if 'toolUse' in item:
                        tool_uses.append(item['toolUse'])

                # 각 도구에 대해 MCP 도구 호출
                tool_results = []
                for tool_use in tool_uses:
                    try:
                        # 도구 이름을 MCP 형식으로 변환 (언더스코어를 대시로)
                        mcp_tool_name = tool_use['name'].replace('_', '-')

                        # MCP 도구 호출
                        result = self.mcp_client.call_tool(mcp_tool_name, tool_use['input'])

                        # 도구 결과 형식화
                        tool_results.append({
                            'toolResult': {
                                'toolUseId': tool_use['toolUseId'],
                                'content': [{'text': json.dumps(result)}],
                                'status': 'success'
                            }
                        })
                    except Exception as e:
                        # 오류 처리
                        tool_results.append({
                            'toolResult': {
                                'toolUseId': tool_use['toolUseId'],
                                'content': [{'text': f'도구 실행 오류: {str(e)}'}],
                                'status': 'error'
                            }
                        })

                # 도구 결과를 추가하여 계속 대화
                if tool_results:
                    self.messages.append({
                        'role': 'user',
                        'content': tool_results
                    })
                    continue  # 다음 반복으로

            # 대화 종료 또는 다른 종료 이유
            elif stop_reason in ['end_turn', 'stop_sequence']:
                final_response = response
                break

            # 토큰 제한에 도달한 경우 계속하도록 요청
            elif stop_reason == 'max_tokens':
                # 이전 메시지의 부분 응답 저장
                partial_response = ""
                for item in output_message.get('content', []):
                    if 'text' in item:
                        partial_response += item['text']

                # 계속 응답하도록 요청
                self.messages.append({
                    'role': 'user',
                    'content': [{'text': '계속해서 응답을 제공해주세요.'}]
                })

                # 동일한 toolConfig 설정으로 계속 호출
                continue

            # 알 수 없는 종료 이유
            else:
                raise Exception(f'알 수 없는 종료 이유: {stop_reason}')

        # 최종 응답 확인 및 비동기 작업 완료 대기
        if final_response:
            return self._check_task_completion(final_response)
        else:
            raise Exception("최대 반복 횟수를 초과했습니다.")

    def process_user_input(self, user_input: str, system_prompt: str = None) -> str:
        """
        사용자 입력 처리 및 최종 텍스트 응답 반환

        Args:
            user_input: 사용자 질문/입력
            system_prompt: 시스템 프롬프트 (선택 사항)

        Returns:
            최종 텍스트 응답
        """
        # 시스템 프롬프트 저장
        if system_prompt:
            self.system_prompt = system_prompt

        # LLM이 모든 필요한 도구를 사용하여 완전한 응답 생성
        response = self.invoke_with_tools(user_input, system_prompt)

        # 응답에서 텍스트 추출
        output_message = response.get('output', {}).get('message', {})
        content = output_message.get('content', [])

        # 모든 텍스트 콘텐츠 결합
        final_text = ""
        for item in content:
            if 'text' in item:
                final_text += item['text']

        return final_text

    def close(self) -> bool:
        """
        MCP 세션 종료

        Returns:
            성공 여부
        """
        return self.mcp_client.close()