import json
import time
import re
import requests
from typing import Dict, Any, List, Optional
from mcp_client import MCPClient


class AnthropicMCPClient:
    """Anthropic API와 통합된 MCP 클라이언트 (SDK 없이 직접 API 호출)"""

    def __init__(self, mcp_url: str, api_key: str = None, model_id: str = None,
                 session_id: str = None, max_retries: int = 5, max_iterations: int = 10):
        """
        Anthropic MCP 클라이언트 초기화

        Args:
            mcp_url: MCP 서버 URL
            api_key: Anthropic API 키
            model_id: Anthropic 모델 ID (기본값: 'claude-3-5-sonnet-20241022')
            session_id: 기존 세션 ID (선택 사항)
            max_retries: 작업 상태 확인을 위한 최대 재시도 횟수
            max_iterations: 도구 호출을 위한 최대 반복 횟수
        """
        self.mcp_client = MCPClient(mcp_url, None, session_id)
        self.model_id = model_id or 'claude-3-5-sonnet-20241022'
        self.api_key = api_key
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.api_headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        self.tools = []
        self.messages = []
        self.max_retries = max_retries
        self.max_iterations = max_iterations
        self.pending_tasks = {}  # 대기 중인 작업 ID 및 상태 추적
        self.system_prompt = None
        self.debug_log = []  # 디버그 로그 추가 - 사고 과정과 도구 사용 추적

    def initialize(self) -> str:
        """
        MCP 세션 초기화 및 도구 목록 로드

        Returns:
            세션 ID
        """
        session_id = self.mcp_client.initialize()
        self.tools = self.mcp_client.list_tools()
        return session_id

    def _convert_tools_format(self):
        """
        MCP 도구 형식을 Anthropic 도구 형식으로 변환

        Returns:
            Anthropic API 형식의 도구 목록
        """
        anthropic_tools = []
        for tool in self.tools:
            # MCP 입력 스키마를 Anthropic 입력 스키마로 변환
            properties = {}
            for prop_name, prop_schema in tool['inputSchema'].get('properties', {}).items():
                properties[prop_name] = {
                    "type": prop_schema.get("type", "string"),
                    "description": prop_schema.get("description", f"{prop_name} 파라미터")
                }

            anthropic_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": tool['inputSchema'].get('required', [])
                }
            })

        return anthropic_tools

    def _check_task_completion(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        응답에서 대기 중인 작업을 확인하고 완료될 때까지 대기

        Args:
            response: Anthropic 모델 응답

        Returns:
            최종 응답
        """
        # 응답 텍스트 추출
        response_text = ""
        if "content" in response:
            if isinstance(response["content"], list):
                for item in response["content"]:
                    if isinstance(item, str):
                        response_text += item
                    elif isinstance(item, dict) and "text" in item:
                        response_text += item["text"]
            elif isinstance(response["content"], str):
                response_text = response["content"]

        # 작업 ID 패턴 탐지
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

        # 디버그 로그에 비동기 작업 감지 기록
        self.debug_log.append({
            "type": "async_task_detected",
            "task_ids": task_ids,
            "timestamp": time.time()
        })

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
                            tool_input = {"execution_arn": task_id}
                        else:
                            tool_input = {"task_id": task_id}

                        # 디버그 로그에 상태 확인 도구 요청 기록
                        self.debug_log.append({
                            "type": "status_check_request",
                            "tool_name": mcp_tool_name,
                            "input": tool_input,
                            "timestamp": time.time()
                        })

                        status_result = self.mcp_client.call_tool(mcp_tool_name, tool_input)
                        status_checked = True

                        # 디버그 로그에 상태 확인 결과 기록
                        self.debug_log.append({
                            "type": "status_check_result",
                            "tool_name": mcp_tool_name,
                            "input": tool_input,
                            "output": status_result,
                            "timestamp": time.time()
                        })

                        # 작업 상태 확인
                        if status_result.get('status') == 'complete':
                            self.pending_tasks[task_id]['status'] = 'complete'
                            self.pending_tasks[task_id]['result'] = status_result

                            # 디버그 로그에 작업 완료 기록
                            self.debug_log.append({
                                "type": "async_task_complete",
                                "task_id": task_id,
                                "result": status_result,
                                "timestamp": time.time()
                            })
                            break
                        elif status_result.get('status') == 'error':
                            self.pending_tasks[task_id]['status'] = 'error'
                            self.pending_tasks[task_id]['error'] = status_result.get('message')

                            # 디버그 로그에 작업 오류 기록
                            self.debug_log.append({
                                "type": "async_task_error",
                                "task_id": task_id,
                                "error": status_result.get('message'),
                                "timestamp": time.time()
                            })
                            break

                        # 여전히 진행 중인 경우 대기
                        time.sleep(2)

                    except Exception as e:
                        # 이 도구가 실패하면 다음 도구로 시도
                        self.debug_log.append({
                            "type": "status_check_error",
                            "tool_name": mcp_tool_name,
                            "error": str(e),
                            "timestamp": time.time()
                        })
                        continue

                # 하나 이상의 도구로 상태를 확인했고 작업이 완료된 경우
                if status_checked and self.pending_tasks[task_id]['status'] in ['complete', 'error']:
                    break

                # 타임아웃 확인 (60초)
                if time.time() - task_info['start_time'] > 60:
                    self.pending_tasks[task_id]['status'] = 'timeout'

                    # 디버그 로그에 작업 타임아웃 기록
                    self.debug_log.append({
                        "type": "async_task_timeout",
                        "task_id": task_id,
                        "timestamp": time.time()
                    })
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

            # 디버그 로그에 최종 분석 요청 기록
            self.debug_log.append({
                "type": "final_analysis_request",
                "content": final_request,
                "timestamp": time.time()
            })

            # 최종 분석 요청
            self.messages.append({
                "role": "user",
                "content": final_request
            })

            # API 요청 페이로드 구성 - max_tokens 필드 추가
            payload = {
                "model": self.model_id,
                "max_tokens": 4096,
                "messages": self.messages
            }

            # 시스템 프롬프트가 있는 경우 추가
            if self.system_prompt:
                payload["system"] = self.system_prompt

            # API 요청 전송
            response = requests.post(
                self.api_url,
                headers=self.api_headers,
                json=payload
            )

            # 응답 파싱
            if response.status_code == 200:
                response_json = response.json()
                content = response_json.get("content", [])
                final_message = ""
                for item in content:
                    if item.get("type") == "text":
                        final_message += item.get("text", "")

                # 디버그 로그에 최종 분석 응답 기록
                self.debug_log.append({
                    "type": "final_analysis_response",
                    "content": final_message,
                    "timestamp": time.time()
                })

                # 메시지에 최종 응답 추가
                self.messages.append({
                    "role": "assistant",
                    "content": final_message
                })

                # 대기 중인 작업 목록 초기화
                self.pending_tasks = {}

                # 표준 형식으로 응답 변환
                return {
                    "output": {
                        "message": {
                            "content": [{"text": final_message}]
                        }
                    }
                }
            else:
                error_message = f"Anthropic API 오류: {response.status_code} - {response.text}"

                # 디버그 로그에 API 오류 기록
                self.debug_log.append({
                    "type": "api_error",
                    "error": error_message,
                    "timestamp": time.time()
                })

                return {
                    "output": {
                        "message": {
                            "content": [{"text": error_message}]
                        }
                    }
                }
        else:
            # 상태 업데이트 요청
            status_summary = "일부 작업이 아직 진행 중입니다. 현재 상태:\n\n"
            for task_id, task_info in self.pending_tasks.items():
                status_summary += f"작업 ID: {task_id}, 상태: {task_info['status']}\n"

            # 디버그 로그에 상태 업데이트 요청 기록
            self.debug_log.append({
                "type": "status_update_request",
                "content": status_summary,
                "timestamp": time.time()
            })

            self.messages.append({
                "role": "user",
                "content": status_summary + "\n계속해서 작업 상태를 확인해주세요."
            })

            # API 요청 페이로드 구성 - max_tokens 필드 추가
            payload = {
                "model": self.model_id,
                "max_tokens": 4096,
                "messages": self.messages
            }

            # 시스템 프롬프트가 있는 경우 추가
            if self.system_prompt:
                payload["system"] = self.system_prompt

            # API 요청 전송
            response = requests.post(
                self.api_url,
                headers=self.api_headers,
                json=payload
            )

            # 응답 파싱
            if response.status_code == 200:
                response_json = response.json()
                content = response_json.get("content", [])
                updated_message = ""
                for item in content:
                    if item.get("type") == "text":
                        updated_message += item.get("text", "")

                # 디버그 로그에 상태 업데이트 응답 기록
                self.debug_log.append({
                    "type": "status_update_response",
                    "content": updated_message,
                    "timestamp": time.time()
                })

                # 메시지에 업데이트된 응답 추가
                self.messages.append({
                    "role": "assistant",
                    "content": updated_message
                })

                # 재귀적으로 작업 완료 확인
                return self._check_task_completion({
                    "content": [updated_message]
                })
            else:
                error_message = f"Anthropic API 오류: {response.status_code} - {response.text}"

                # 디버그 로그에 API 오류 기록
                self.debug_log.append({
                    "type": "api_error",
                    "error": error_message,
                    "timestamp": time.time()
                })

                return {
                    "output": {
                        "message": {
                            "content": [{"text": error_message}]
                        }
                    }
                }

    def invoke_with_tools(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        """
        MCP 도구를 사용하여 Anthropic 모델 호출

        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택 사항)

        Returns:
            Anthropic 모델 응답 (표준 형식으로 변환됨)
        """
        # 세션 및 도구가 초기화되지 않은 경우
        if not self.tools:
            self.initialize()

        # 시스템 프롬프트 저장 (나중에 재사용)
        if system_prompt:
            self.system_prompt = system_prompt

        # 메시지 배열 초기화
        if not self.messages:
            self.messages = []

        # 디버그 로그 초기화
        self.debug_log = []

        # 디버그 로그에 사용자 입력 기록
        self.debug_log.append({
            "type": "user_input",
            "content": prompt,
            "timestamp": time.time()
        })

        # 시스템 프롬프트가 있는 경우 디버그 로그에 기록
        if system_prompt:
            self.debug_log.append({
                "type": "system_prompt",
                "content": system_prompt,
                "timestamp": time.time()
            })

        # 메시지 추가
        self.messages.append({
            "role": "user",
            "content": prompt
        })

        # Anthropic 도구 형식으로 변환
        anthropic_tools = self._convert_tools_format()

        # 디버그 로그에 사용 가능한 도구 기록
        self.debug_log.append({
            "type": "available_tools",
            "tools": [tool["name"] for tool in anthropic_tools],
            "timestamp": time.time()
        })

        # 모델 호출 루프 시작 (도구 사용이 완료될 때까지)
        final_response = None
        iteration = 0

        # 모든 도구 결과 응답을 저장할 배열
        all_responses = []

        print(f"대화 시작 - 메시지 수: {len(self.messages)}")
        while iteration < self.max_iterations:
            iteration += 1
            print(f"반복 {iteration}/{self.max_iterations}")

            # 디버그 로그에 반복 정보 기록
            self.debug_log.append({
                "type": "iteration_start",
                "iteration": iteration,
                "timestamp": time.time()
            })

            # API 요청 페이로드 구성 - max_tokens 필드 추가
            payload = {
                "model": self.model_id,
                "max_tokens": 4096,
                "messages": self.messages
            }

            # 도구가 있는 경우 추가
            if anthropic_tools:
                payload["tools"] = anthropic_tools

            # 시스템 프롬프트가 있는 경우 추가
            if system_prompt:
                payload["system"] = system_prompt

            # 디버깅을 위한 로깅 추가
            print(f"API 요청 페이로드: {json.dumps(payload, indent=2, ensure_ascii=False)[:500]}...")

            # API 요청 전송
            response = requests.post(
                self.api_url,
                headers=self.api_headers,
                json=payload
            )

            # 디버깅을 위한 응답 로깅
            print(f"API 응답 상태 코드: {response.status_code}")
            print(f"API 응답 내용: {response.text[:500]}...")

            # 응답 파싱
            if response.status_code != 200:
                error_message = f"Anthropic API 오류: {response.status_code} - {response.text}"

                # 디버그 로그에 API 오류 기록
                self.debug_log.append({
                    "type": "api_error",
                    "error": error_message,
                    "timestamp": time.time()
                })

                return {
                    "output": {
                        "message": {
                            "content": [{"text": error_message}]
                        }
                    }
                }

            response_json = response.json()
            content = response_json.get("content", [])
            message_content = ""
            tool_uses = []

            # 응답 콘텐츠에서 텍스트와 도구 사용 분리
            for item in content:
                if item.get("type") == "text":
                    message_content += item.get("text", "")
                elif item.get("type") == "tool_use":
                    tool_uses.append(item)

            # 응답 저장
            print(f"응답 텍스트: {message_content[:100]}...")
            print(f"도구 사용 요청 수: {len(tool_uses)}")

            # 디버그 로그에 모델 응답 기록
            if message_content:
                self.debug_log.append({
                    "type": "model_reasoning",
                    "content": message_content,
                    "timestamp": time.time()
                })

            # 텍스트 응답이 있으면 저장
            if message_content:
                all_responses.append(message_content)

            # 메시지에 응답 추가 (텍스트만 추가)
            if message_content:
                print(f"텍스트 응답 추가: {message_content[:100]}...")
                self.messages.append({
                    "role": "assistant",
                    "content": message_content
                })

            # 도구 사용 요청이 있는 경우
            if tool_uses:
                # 디버그 로그에 도구 사용 요청 기록
                self.debug_log.append({
                    "type": "tool_use_requests",
                    "count": len(tool_uses),
                    "timestamp": time.time()
                })

                # 각 도구에 대해 MCP 도구 호출
                tool_results = []
                for tool_use in tool_uses:
                    try:
                        # 도구 정보 추출
                        tool_use_id = tool_use.get("id")
                        tool_name = tool_use.get("name")
                        tool_input = tool_use.get("input", {})

                        print(f"도구 호출: {tool_name}, 입력: {json.dumps(tool_input, ensure_ascii=False)}")

                        # 디버그 로그에 도구 사용 요청 기록
                        self.debug_log.append({
                            "type": "tool_request",
                            "tool_name": tool_name,
                            "input": tool_input,
                            "timestamp": time.time()
                        })

                        # MCP 도구 호출
                        result = self.mcp_client.call_tool(
                            tool_name,
                            tool_input
                        )

                        print(f"도구 결과: {json.dumps(result, ensure_ascii=False)[:200]}...")

                        # 디버그 로그에 도구 결과 기록
                        self.debug_log.append({
                            "type": "tool_result",
                            "tool_name": tool_name,
                            "input": tool_input,
                            "output": result,
                            "timestamp": time.time()
                        })

                        # 도구 결과를 저장
                        tool_results.append({
                            "tool_id": tool_use_id,
                            "name": tool_name,
                            "result": result
                        })
                    except Exception as e:
                        # 오류 처리
                        print(f"도구 호출 오류: {str(e)}")

                        # 디버그 로그에 도구 오류 기록
                        self.debug_log.append({
                            "type": "tool_error",
                            "tool_name": tool_name,
                            "input": tool_input,
                            "error": str(e),
                            "timestamp": time.time()
                        })

                        tool_results.append({
                            "tool_id": tool_use_id,
                            "name": tool_name,
                            "error": str(e)
                        })

                # 도구 결과를 새로운 사용자 메시지로 추가
                if tool_results:
                    tool_result_messages = []
                    for result in tool_results:
                        if "error" in result:
                            tool_result_messages.append(
                                f"도구: {result['name']}\n오류: {result['error']}"
                            )
                        else:
                            tool_result_messages.append(
                                f"도구: {result['name']}\n결과: {json.dumps(result['result'], ensure_ascii=False)}"
                            )

                    # 도구 결과를 사용자 메시지로 추가
                    tool_result_message = "다음은 도구 호출 결과입니다:\n\n" + "\n\n".join(tool_result_messages)
                    print(f"도구 결과를 사용자 메시지로 추가: {len(tool_results)}개")

                    # 디버그 로그에 도구 결과 요약 기록
                    self.debug_log.append({
                        "type": "tool_results_summary",
                        "content": tool_result_message,
                        "timestamp": time.time()
                    })

                    self.messages.append({
                        "role": "user",
                        "content": tool_result_message
                    })
                    continue  # 다음 반복으로

            # 도구 호출이 없는 경우 최종 응답 설정 및 루프 종료
            else:
                print("도구 호출 없음, 대화 종료")

                # 디버그 로그에 대화 종료 기록
                self.debug_log.append({
                    "type": "conversation_complete",
                    "iteration": iteration,
                    "timestamp": time.time()
                })

                final_response = {
                    "content": [message_content]
                }
                break

        # 최종 응답이 없으면 오류 발생
        if not final_response and all_responses:
            # 모든 응답을 결합하여 최종 응답 생성
            combined_response = " ".join(all_responses)
            final_response = {
                "content": [combined_response]
            }
            print(f"최종 응답 생성: {combined_response[:100]}...")

            # 디버그 로그에 결합된 응답 기록
            self.debug_log.append({
                "type": "combined_response",
                "content": combined_response,
                "timestamp": time.time()
            })
        elif not final_response:
            error_message = "최대 반복 횟수를 초과했습니다."

            # 디버그 로그에 반복 횟수 초과 오류 기록
            self.debug_log.append({
                "type": "max_iterations_exceeded",
                "error": error_message,
                "timestamp": time.time()
            })
            raise Exception(error_message)

        # 비동기 작업 완료 확인
        return self._check_task_completion(final_response)

    def _extract_text_from_response(self, response):
        """
        응답에서 텍스트 추출

        Args:
            response: Anthropic 응답 객체

        Returns:
            추출된 텍스트
        """
        if "content" in response:
            if isinstance(response["content"], list):
                text = ""
                for item in response["content"]:
                    if isinstance(item, str):
                        text += item
                    elif isinstance(item, dict) and "text" in item:
                        text += item["text"]
                return text
            elif isinstance(response["content"], str):
                return response["content"]

        output_message = response.get('output', {}).get('message', {})
        if output_message:
            content = output_message.get('content', [])
            if content:
                text = ""
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text += item["text"]
                return text

        return str(response)

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

        # 메시지 배열 초기화
        self.messages = []

        # 디버그 로그 초기화
        self.debug_log = []

        # 디버그 로그에 처리 시작 기록
        self.debug_log.append({
            "type": "process_start",
            "user_input": user_input,
            "timestamp": time.time()
        })

        # LLM이 모든 필요한 도구를 사용하여 완전한 응답 생성
        response = self.invoke_with_tools(user_input, system_prompt)

        # 응답에서 텍스트 추출
        output_message = response.get('output', {}).get('message', {})
        content = output_message.get('content', [])

        # 모든 텍스트 콘텐츠 결합
        final_text = ""
        for item in content:
            if isinstance(item, dict) and 'text' in item:
                final_text += item['text']
            elif isinstance(item, str):
                final_text += item

        # 최종 텍스트 로깅 추가
        print(f"최종 응답 반환: {final_text[:200]}...")

        # 디버그 로그에 최종 응답 기록
        self.debug_log.append({
            "type": "final_response",
            "content": final_text,
            "timestamp": time.time()
        })

        # 메시지 배열에서 마지막 assistant 응답 찾기
        if not final_text:
            for message in reversed(self.messages):
                if message.get("role") == "assistant":
                    final_text = message.get("content", "")
                    print(f"마지막 assistant 메시지 사용: {final_text[:200]}...")
                    break

        return final_text

    def get_debug_log(self) -> List[Dict[str, Any]]:
        """
        디버그 로그 반환

        Returns:
            디버그 로그 배열
        """
        return self.debug_log

    def close(self) -> bool:
        """
        MCP 세션 종료

        Returns:
            성공 여부
        """
        return self.mcp_client.close()
