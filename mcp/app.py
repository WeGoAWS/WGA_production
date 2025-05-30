import os
import json
import boto3
import pandas as pd
import httpx
import re
import requests
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict, List, Any, Union
from tabulate import tabulate
from pydantic import BaseModel, Field
from lambda_mcp.lambda_mcp import LambdaMCPServer
from lambda_mcp.document_utils import (
    extract_content_from_html,
    format_documentation_result,
    is_html_content,
    parse_recommendation_results,
)
from lambda_mcp.diagram_utils import (
    generate_diagram,
    get_diagram_examples,
    list_diagram_icons
)
from lambda_mcp.mcp_types import DiagramType
from lambda_mcp.chart_utils import generate_chart_url, validate_chart_data
from lambda_mcp.logs_utils import generate_insights_query, analyze_insights_results, get_query_templates

# API URL 상수 정의
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 ModelContextProtocol/1.0 (AWS Documentation Server)'
SEARCH_API_URL = 'https://proxy.search.docs.aws.amazon.com/search'
RECOMMENDATIONS_API_URL = 'https://contentrecs-api.docs.aws.amazon.com/v1/recommendations'


# Get session table name from environment variable
session_table = os.environ.get('MCP_SESSION_TABLE', f'wga-mcp-sessions-{os.environ.get("ENV", "dev")}')
aws_region = os.environ.get("AWS_REGION", "us-east-1")

# Create AWS service clients
cloudwatch_client = boto3.client('cloudwatch', region_name=aws_region)
cloudtrail_client = boto3.client('cloudtrail', region_name=aws_region)
logs_client = boto3.client('logs', region_name=aws_region)
xray_client = boto3.client('xray', region_name=aws_region)
autoscaling_client = boto3.client('autoscaling', region_name=aws_region)
ec2_client = boto3.client('ec2', region_name=aws_region)
health_client = boto3.client('health', region_name=aws_region)
ce_client = boto3.client('ce', region_name=aws_region)

# Initialize the MCP server
mcp_server = LambdaMCPServer(name="cloudguard", version="1.0.0", session_table=session_table)

"""
This file contains the server information for enabling our application
with tools that the model can access using MCP. This is the first server that 
focuses on the monitoring aspect of the application. This means that this server
code has tools to fetch cloudwatch logs for a given service provided by the user.

The workflow that is followed in this server is: The tool provides users with
the available services that they can monitor, then get the most recent cloudwatch logs for 
that given service, and then check for the cloudwatch alarms. This information is then used
by the other server to take further steps, such as diagnose the issue and then a resolution agent
to create tickets.
"""

@mcp_server.tool()
def fetch_cloudwatch_logs_for_service(
        service_name: str,
        days: int = 3,
        filter_pattern: str = ""
) -> Dict[str, Any]:
    """
    Fetches CloudWatch logs for a specified service for the given number of days.

    Args:
        service_name: The name of the service to fetch logs for (e.g., "ec2", "lambda", "rds")
        days: Number of days of logs to fetch (default: 3)
        filter_pattern: Optional CloudWatch Logs filter pattern

    Returns:
        Dictionary with log groups and their recent log events
    """
    try:
        service_log_prefixes = {
            "ec2": ["/aws/ec2", "/var/log"],
            "lambda": ["/aws/lambda"],
            "rds": ["/aws/rds"],
            "eks": ["/aws/eks"],
            "apigateway": ["/aws/apigateway", "API-Gateway-Execution-Logs"],
            "cloudtrail": ["/aws/cloudtrail"],
            "s3": ["/aws/s3", "/aws/s3-access"],
            "vpc": ["/aws/vpc"],
            "waf": ["/aws/waf"],
            "bedrock": [f"/aws/bedrock/modelinvocations"],
            "iam": ["/aws/dummy-security-logs"],
            "guardduty": ["/aws/guardduty"]
        }

        # Default to searching all log groups if service isn't in our mapping
        prefixes = service_log_prefixes.get(service_name.lower(), [""])

        # Find all log groups for this service
        log_groups = []
        for prefix in prefixes:
            paginator = logs_client.get_paginator('describe_log_groups')
            for page in paginator.paginate(logGroupNamePrefix=prefix):
                log_groups.extend([group['logGroupName'] for group in page['logGroups']])

        if not log_groups:
            return {"status": "warning", "message": f"No log groups found for service: {service_name}"}

        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        # Convert to milliseconds since epoch
        start_time_ms = int(start_time.timestamp() * 1000)
        end_time_ms = int(end_time.timestamp() * 1000)

        results = {}

        # Iterate through log groups and fetch log events
        for log_group in log_groups:
            try:
                # First get log streams
                response = logs_client.describe_log_streams(
                    logGroupName=log_group,
                    orderBy='LastEventTime',
                    descending=True,
                    limit=5  # Get the 5 most recent streams
                )
                streams = response.get('logStreams', [])

                if not streams:
                    results[log_group] = {"status": "info", "message": "No log streams found"}
                    continue

                group_events = []

                # For each stream, get recent log events
                for stream in streams:
                    stream_name = stream['logStreamName']

                    # If filter pattern is provided, use filter_log_events
                    if filter_pattern:
                        filter_response = logs_client.filter_log_events(
                            logGroupName=log_group,
                            logStreamNames=[stream_name],
                            startTime=start_time_ms,
                            endTime=end_time_ms,
                            filterPattern=filter_pattern,
                            limit=100
                        )
                        events = filter_response.get('events', [])
                    else:
                        # Otherwise use get_log_events
                        log_response = logs_client.get_log_events(
                            logGroupName=log_group,
                            logStreamName=stream_name,
                            startTime=start_time_ms,
                            endTime=end_time_ms,
                            limit=100
                        )
                        events = log_response.get('events', [])

                    # Process and add events
                    for event in events:
                        # Convert timestamp to readable format
                        timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                        formatted_event = {
                            'timestamp': timestamp.isoformat(),
                            'message': event['message']
                        }
                        group_events.append(formatted_event)

                # Sort all events by timestamp (newest first)
                group_events.sort(key=lambda x: x['timestamp'], reverse=True)

                results[log_group] = {
                    "status": "success",
                    "events_count": len(group_events),
                    "events": group_events[:100]  # Limit to 100 most recent events
                }

            except Exception as e:
                results[log_group] = {"status": "error", "message": str(e)}

        return {
            "service": service_name,
            "time_range": f"{start_time.isoformat()} to {end_time.isoformat()}",
            "log_groups_count": len(log_groups),
            "log_groups": results
        }

    except Exception as e:
        print(f"Error fetching logs for service {service_name}: {e}")
        return {"status": "error", "message": str(e)}


@mcp_server.tool()
def list_cloudwatch_dashboards() -> Dict[str, Any]:
    """
    Lists all CloudWatch dashboards in the AWS account.

    Returns:
        A dictionary containing the list of dashboard names and their ARNs.
    """
    try:
        dashboards = []
        paginator = cloudwatch_client.get_paginator('list_dashboards')
        for page in paginator.paginate():
            for entry in page.get('DashboardEntries', []):
                dashboards.append({
                    'DashboardName': entry.get('DashboardName'),
                    'DashboardArn': entry.get('DashboardArn')
                })

        return {
            'status': 'success',
            'dashboard_count': len(dashboards),
            'dashboards': dashboards
        }

    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@mcp_server.tool()
def get_cloudwatch_alarms_for_service(service_name: str = None) -> Dict[str, Any]:
    """
    Fetches CloudWatch alarms, optionally filtering by service.

    Args:
        service_name: The name of the service to filter alarms for

    Returns:
        Dictionary with alarm information
    """
    try:
        response = cloudwatch_client.describe_alarms()
        alarms = response.get('MetricAlarms', [])

        formatted_alarms = []
        for alarm in alarms:
            namespace = alarm.get('Namespace', '').lower()

            # Filter by service if provided
            if service_name and service_name.lower() not in namespace:
                continue

            formatted_alarms.append({
                'name': alarm.get('AlarmName'),
                'state': alarm.get('StateValue'),
                'metric': alarm.get('MetricName'),
                'namespace': alarm.get('Namespace')
            })

        return {
            "alarm_count": len(formatted_alarms),
            "alarms": formatted_alarms
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp_server.tool()
def get_dashboard_summary(dashboard_name: str) -> Dict[str, Any]:
    """
    Retrieves and summarizes the configuration of a specified CloudWatch dashboard.

    Args:
        dashboard_name: The name of the CloudWatch dashboard.

    Returns:
        A summary of the dashboard's widgets and their configurations.
    """
    try:
        # Fetch the dashboard configuration
        response = cloudwatch_client.get_dashboard(DashboardName=dashboard_name)
        dashboard_body = response.get('DashboardBody', '{}')
        dashboard_config = json.loads(dashboard_body)

        # Summarize the widgets in the dashboard
        widgets_summary = []
        for widget in dashboard_config.get('widgets', []):
            widget_summary = {
                'type': widget.get('type'),
                'x': widget.get('x'),
                'y': widget.get('y'),
                'width': widget.get('width'),
                'height': widget.get('height'),
                'properties': widget.get('properties', {})
            }
            widgets_summary.append(widget_summary)

        return {
            'dashboard_name': dashboard_name,
            'widgets_count': len(widgets_summary),
            'widgets_summary': widgets_summary
        }

    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@mcp_server.tool()
def list_log_groups(prefix: str = "") -> Dict[str, Any]:
    """
    Lists all CloudWatch log groups, optionally filtered by a prefix.

    Args:
        prefix: Optional prefix to filter log groups

    Returns:
        Dictionary with list of log groups and their details
    """
    try:
        log_groups = []
        paginator = logs_client.get_paginator('describe_log_groups')

        # Use the prefix if provided, otherwise get all log groups
        if prefix:
            pages = paginator.paginate(logGroupNamePrefix=prefix)
        else:
            pages = paginator.paginate()

        # Collect all log groups from paginated results
        for page in pages:
            for group in page.get('logGroups', []):
                log_groups.append({
                    'name': group.get('logGroupName'),
                    'arn': group.get('arn'),
                    'stored_bytes': group.get('storedBytes'),
                    'creation_time': datetime.fromtimestamp(
                        group.get('creationTime', 0) / 1000
                    ).isoformat() if group.get('creationTime') else None,
                    'retention_in_days': group.get('retentionInDays')
                })

        # Sort log groups by name
        log_groups.sort(key=lambda x: x['name'])

        return {
            "status": "success",
            "group_count": len(log_groups),
            "log_groups": log_groups
        }

    except Exception as e:
        print(f"Error listing log groups: {e}")
        return {"status": "error", "message": str(e)}


@mcp_server.tool()
def analyze_log_group(
        log_group_name: str,
        days: int = 1,
        max_events: int = 1000,
        filter_pattern: str = ""
) -> Dict[str, Any]:
    """
    Analyzes a specific CloudWatch log group and provides insights.

    Args:
        log_group_name: The name of the log group to analyze
        days: Number of days of logs to analyze (default: 1)
        max_events: Maximum number of events to retrieve (default: 1000)
        filter_pattern: Optional CloudWatch Logs filter pattern

    Returns:
        Dictionary with analysis and insights about the log group
    """
    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        # Convert to milliseconds since epoch
        start_time_ms = int(start_time.timestamp() * 1000)
        end_time_ms = int(end_time.timestamp() * 1000)

        print(f"Analyzing log group: {log_group_name}")
        print(f"Time range: {start_time.isoformat()} to {end_time.isoformat()}")

        # Get log streams
        streams_response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=10  # Get the 10 most recent streams
        )
        streams = streams_response.get('logStreams', [])

        if not streams:
            return {
                "status": "info",
                "message": f"No log streams found in log group: {log_group_name}"
            }

        # Collect events from all streams
        all_events = []

        # For each stream, get log events
        for stream in streams:
            stream_name = stream['logStreamName']

            # If filter pattern is provided, use filter_log_events
            if filter_pattern:
                filter_response = logs_client.filter_log_events(
                    logGroupName=log_group_name,
                    logStreamNames=[stream_name],
                    startTime=start_time_ms,
                    endTime=end_time_ms,
                    filterPattern=filter_pattern,
                    limit=max_events // len(streams)  # Divide limit among streams
                )
                events = filter_response.get('events', [])
            else:
                # Otherwise use get_log_events
                log_response = logs_client.get_log_events(
                    logGroupName=log_group_name,
                    logStreamName=stream_name,
                    startTime=start_time_ms,
                    endTime=end_time_ms,
                    limit=max_events // len(streams)
                )
                events = log_response.get('events', [])

            # Process and add events
            for event in events:
                # Convert timestamp to readable format
                timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                formatted_event = {
                    'timestamp': timestamp.isoformat(),
                    'message': event['message'],
                    'stream': stream_name
                }
                all_events.append(formatted_event)

        # Sort all events by timestamp (newest first)
        all_events.sort(key=lambda x: x['timestamp'], reverse=True)

        # Analyze the events
        insights = {
            "event_count": len(all_events),
            "time_range": f"{start_time.isoformat()} to {end_time.isoformat()}",
            "unique_streams": len(set(event['stream'] for event in all_events)),
            "most_recent_event": all_events[0]['timestamp'] if all_events else None,
            "oldest_event": all_events[-1]['timestamp'] if all_events else None,
        }

        # Count error, warning, info level events
        error_count = sum(1 for event in all_events if 'error' in event['message'].lower())
        warning_count = sum(1 for event in all_events if 'warn' in event['message'].lower())
        info_count = sum(1 for event in all_events if 'info' in event['message'].lower())

        insights["event_levels"] = {
            "error": error_count,
            "warning": warning_count,
            "info": info_count,
            "other": len(all_events) - error_count - warning_count - info_count
        }

        # Group events by hour to see distribution
        hour_distribution = {}
        for event in all_events:
            hour = event['timestamp'][:13]  # Format: YYYY-MM-DDTHH
            hour_distribution[hour] = hour_distribution.get(hour, 0) + 1

        insights["hourly_distribution"] = hour_distribution

        # Find common patterns in log messages
        # Extract first 5 words from each message as a pattern
        patterns = {}
        for event in all_events:
            words = event['message'].split()
            if len(words) >= 5:
                pattern = ' '.join(words[:5])
                patterns[pattern] = patterns.get(pattern, 0) + 1

        # Get top 10 patterns
        top_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:10]
        insights["common_patterns"] = [{"pattern": p, "count": c} for p, c in top_patterns]

        # Sample recent events
        insights["sample_events"] = all_events[:20]  # First 20 events for reference

        return {
            "status": "success",
            "log_group": log_group_name,
            "insights": insights
        }

    except Exception as e:
        print(f"Error analyzing log group {log_group_name}: {e}")
        return {"status": "error", "message": str(e)}


@mcp_server.tool()
def analyze_log_groups_insights(
        log_groups: str,
        query: str = "",
        days: int = 1,
        max_results: int = 1000,
        analysis_type: str = "custom"
) -> Dict[str, Any]:
    """
    CloudWatch Logs Insights를 사용하여 로그 그룹을 분석합니다.

    이 함수는 AWS CloudWatch Logs Insights의 강력한 쿼리 엔진을 활용하여
    대용량 로그 데이터를 효율적으로 분석하고 인사이트를 자동으로 생성합니다.

    ## 언제 사용해야 하나요?
    - 사용자가 "로그 분석", "에러 패턴", "성능 모니터링", "보안 이벤트" 등을 요청할 때
    - 특정 시간대의 로그를 심층 분석해야 할 때
    - 여러 서비스의 로그를 통합 분석해야 할 때
    - 복잡한 로그 쿼리가 필요한 고급 분석 요청시

    ## 주요 분석 유형별 활용법:

    ### 1. 에러 분석 (analysis_type="errors")
    - 사용 케이스: "최근 에러 패턴을 분석해줘", "어떤 에러가 가장 많이 발생했나?"
    - 자동 분석: 에러 패턴 분류, 빈도 분석, 시간대별 분포
    - 로그 그룹: Lambda, API Gateway, 애플리케이션 로그

    ### 2. 성능 분석 (analysis_type="performance")
    - 사용 케이스: "Lambda 함수 성능을 분석해줘", "응답 시간이 느린 요청 찾아줘"
    - 자동 분석: 평균/최대/최소 응답시간, 성능 추세
    - 로그 그룹: Lambda, API Gateway 로그

    ### 3. 보안 분석 (analysis_type="security")
    - 사용 케이스: "보안 이벤트 분석해줘", "의심스러운 IP 찾아줘"
    - 자동 분석: 실패한 접근 시도, 의심스러운 IP, 보안 패턴
    - 로그 그룹: CloudTrail, WAF, 보안 관련 로그

    ### 4. 로그인 분석 (analysis_type="login")
    - 사용 케이스: "콘솔 로그인 분석해줘", "실패한 로그인 시도 확인해줘"
    - 자동 분석: 로그인 성공/실패, 의심스러운 IP, 사용자별 통계
    - 로그 그룹: CloudTrail 로그 (ConsoleLogin 이벤트 포함)

    ### 5. 트래픽 분석 (analysis_type="traffic")
    - 사용 케이스: "트래픽 패턴 분석해줘", "시간대별 요청량 확인해줘"
    - 자동 분석: 시간대별 요청량, 트래픽 추세
    - 로그 그룹: API Gateway, CloudFront, ALB 로그

    ## 사용자 질문 예시와 대응 방법:

    ### 질문: "지난 주 Lambda 에러를 분석해줘"
    ```python
    analyze_log_groups_insights(
        log_groups="/aws/lambda/my-function",
        analysis_type="errors",
        days=7
    )
    ```

    ### 질문: "API Gateway와 Lambda를 함께 성능 분석해줘"
    ```python
    analyze_log_groups_insights(
        log_groups="/aws/apigateway/my-api,/aws/lambda/my-function",
        analysis_type="performance",
        days=1
    )
    ```

    ### 질문: "CloudTrail에서 콘솔 로그인 실패 분석해줘"
    ```python
    analyze_log_groups_insights(
        log_groups="/aws/cloudtrail/logs",
        analysis_type="login",
        days=7
    )
    ```

    ### 질문: "특정 에러 메시지만 찾아줘" (커스텀 쿼리)
    ```python
    analyze_log_groups_insights(
        log_groups="/aws/lambda/my-function",
        query='''
            fields @timestamp, @message, @requestId
            | filter @message like /ConnectionError/
            | sort @timestamp desc
            | limit 100
        ''',
        days=1
    )
    ```

    ## 로그 그룹 이름 가이드:
    - Lambda: "/aws/lambda/함수이름"
    - API Gateway: "/aws/apigateway/api이름" 또는 "API-Gateway-Execution-Logs_API아이디/stage"
    - CloudTrail: "/aws/cloudtrail/로그그룹이름"
    - ECS: "/aws/ecs/cluster/클러스터이름"
    - VPC Flow Logs: "/aws/vpc/flowlogs"

    ## 응답 해석 가이드:
    - `analysis_summary.insights`: 자동 생성된 핵심 인사이트
    - `results`: 실제 쿼리 결과 (최대 50개 샘플)
    - `statistics`: 스캔된 레코드 수, 매칭된 레코드 수 등
    - `field_names`: 결과에 포함된 필드 목록

    ## 팁:
    - 여러 로그 그룹을 쉼표로 구분하여 통합 분석 가능
    - days를 길게 설정하면 더 많은 데이터 분석 (단, 시간 증가)
    - 복잡한 분석이 필요하면 custom 쿼리 직접 작성
    - 결과가 너무 많으면 max_results로 제한

    Args:
        log_groups: 분석할 로그 그룹 이름들 (쉼표로 구분, 예: "/aws/lambda/func1,/aws/apigateway/api1")
        query: Logs Insights 쿼리 (비어있으면 analysis_type에 따라 자동 생성)
        days: 분석할 일수 (기본값: 1)
        max_results: 최대 결과 수 (기본값: 1000)
        analysis_type: 자동 쿼리 유형 ("errors", "performance", "security", "traffic", "login", "custom")

    Returns:
        Dictionary with analysis results and insights
    """
    try:
        # 로그 그룹 리스트 파싱
        log_group_list = [lg.strip() for lg in log_groups.split(',') if lg.strip()]

        if not log_group_list:
            return {"status": "error", "message": "로그 그룹을 지정해야 합니다."}

        # 시간 범위 계산
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())

        # 쿼리 자동 생성 또는 사용자 쿼리 사용
        if not query:
            query = generate_insights_query(analysis_type)

        print(f"Logs Insights 쿼리 실행: {query}")
        print(f"로그 그룹: {log_group_list}")
        print(f"시간 범위: {start_time.isoformat()} to {end_time.isoformat()}")

        # Logs Insights 쿼리 실행
        response = logs_client.start_query(
            logGroupNames=log_group_list,
            startTime=start_timestamp,
            endTime=end_timestamp,
            queryString=query,
            limit=max_results
        )

        query_id = response['queryId']
        print(f"쿼리 ID: {query_id}")

        # 쿼리 완료 대기
        max_wait_time = 300  # 5분 최대 대기
        wait_time = 0

        while wait_time < max_wait_time:
            result_response = logs_client.get_query_results(queryId=query_id)
            status = result_response['status']

            print(f"쿼리 상태: {status}")

            if status == 'Complete':
                break
            elif status in ['Failed', 'Cancelled', 'Timeout']:
                return {
                    "status": "error",
                    "message": f"쿼리 실행 실패: {status}",
                    "query_id": query_id
                }

            time.sleep(2)
            wait_time += 2

        if wait_time >= max_wait_time:
            return {
                "status": "error",
                "message": "쿼리 실행 시간 초과",
                "query_id": query_id
            }

        # 결과 처리
        results = result_response.get('results', [])
        statistics = result_response.get('statistics', {})

        # 결과를 구조화된 형태로 변환
        structured_results = []
        field_names = set()

        for result_row in results:
            row_data = {}
            for field in result_row:
                field_name = field.get('field', '')
                field_value = field.get('value', '')
                if field_name:
                    row_data[field_name] = field_value
                    field_names.add(field_name)
            if row_data:
                structured_results.append(row_data)

        # 분석 결과 생성
        analysis_summary = analyze_insights_results(
            structured_results, analysis_type, field_names
        )

        return {
            "status": "success",
            "query_id": query_id,
            "analysis_type": analysis_type,
            "log_groups": log_group_list,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "days": days
            },
            "query": query,
            "statistics": {
                "records_matched": statistics.get('recordsMatched', 0),
                "records_scanned": statistics.get('recordsScanned', 0),
                "bytes_scanned": statistics.get('bytesScanned', 0)
            },
            "results_count": len(structured_results),
            "field_names": list(field_names),
            "results": structured_results[:50],  # 최대 50개 결과만 반환
            "analysis_summary": analysis_summary
        }

    except Exception as e:
        print(f"Logs Insights 분석 오류: {str(e)}")
        return {
            "status": "error",
            "message": f"분석 실행 중 오류 발생: {str(e)}"
        }


@mcp_server.tool()
def get_insights_query_templates() -> Dict[str, Any]:
    """
    CloudWatch Logs Insights에서 사용할 수 있는 쿼리 템플릿을 반환합니다.

    ## 언제 사용하나요?
    - 사용자가 "어떤 쿼리 템플릿이 있나요?" 또는 "쿼리 예시 보여줘"라고 물을 때
    - 사용자가 직접 쿼리를 작성하고 싶어할 때 참고 자료로 제공
    - analyze_log_groups_insights()에서 지원하지 않는 특수한 분석이 필요할 때

    ## 주요 템플릿 활용법:

    ### error_analysis
    - 목적: 에러 및 예외 이벤트 시간대별 분석
    - 활용: "에러가 언제 가장 많이 발생했는지 시간대별로 보여줘"

    ### performance_monitoring
    - 목적: Lambda 함수 성능 메트릭 분석
    - 활용: "Lambda 함수 실행 시간과 메모리 사용량 추이 분석"

    ### api_gateway_analysis
    - 목적: API Gateway 4xx/5xx 에러 분석
    - 활용: "API 에러 상태코드별 통계와 HTTP 메소드별 분석"

    ### cloudtrail_security
    - 목적: CloudTrail 보안 이벤트 분석
    - 활용: "위험한 작업(삭제, 종료)과 에러가 있는 이벤트 분석"

    ### console_login_analysis
    - 목적: AWS 콘솔 로그인 이벤트 상세 분석
    - 활용: "콘솔 로그인 성공/실패 이벤트 시간순 조회"

    ### failed_console_logins
    - 목적: 실패한 콘솔 로그인만 집중 분석
    - 활용: "로그인 실패 시도를 IP와 사용자별로 집계"

    ### suspicious_login_patterns
    - 목적: 의심스러운 로그인 패턴 탐지
    - 활용: "시간대별로 로그인 시도가 많은 IP 주소 찾기"

    ## 사용자 질문 예시:

    ### 질문: "API Gateway 에러 분석 쿼리 보여줘"
    ```python
    templates = get_insights_query_templates()
    api_query = templates["api_gateway_analysis"]
    # 이 쿼리를 analyze_log_groups_insights()의 query 파라미터에 사용
    ```

    ### 질문: "Lambda 성능 모니터링 쿼리를 수정해서 1시간 단위로 보고싶어"
    ```python
    templates = get_insights_query_templates()
    custom_query = templates["performance_monitoring"].replace("bin(5m)", "bin(1h)")
    ```

    ### 질문: "보안 이벤트 쿼리를 기반으로 특정 사용자만 필터링하고 싶어"
    ```python
    templates = get_insights_query_templates()
    base_query = templates["cloudtrail_security"]
    # 쿼리에 "| filter userIdentity.userName = 'specific-user'" 추가하여 커스텀
    ```

    ## 템플릿 커스터마이징 팁:
    - bin() 함수로 시간 간격 조절 (5m, 1h, 1d 등)
    - filter 조건 추가로 특정 조건 필터링
    - stats 함수로 다양한 집계 (count, avg, max, min 등)
    - sort 조건 변경으로 정렬 기준 조정
    - limit 값 변경으로 결과 수 제한

    Returns:
        Dictionary with query templates:
        - Key: 템플릿 이름 (예: "error_analysis")
        - Value: Logs Insights 쿼리 문자열 또는 메타데이터
    """
    return get_query_templates()

@mcp_server.tool()
def get_detailed_breakdown_by_day(days: int = 7) -> Dict[str, Any]:
    """
    Retrieve daily spend breakdown by region, service, and instance type.

    Args:
        params: Parameters specifying the number of days to look back

    Returns:
        Dict[str, Any]: A tuple containing:
            - A nested dictionary with cost data organized by date, region, and service
            - A string containing the formatted output report
    """

    # Calculate the time period
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # Initialize output buffer
    output_buffer = []

    try:
        output_buffer.append(f"\nDetailed Cost Breakdown by Region, Service, and Instance Type ({days} days):")
        output_buffer.append("-" * 75)

        # First get the daily costs by region and service
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'REGION'
                },
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }
            ]
        )

        # Create data structure to hold the results
        all_data = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

        # Process the results
        for time_data in response['ResultsByTime']:
            date = time_data['TimePeriod']['Start']

            output_buffer.append(f"\nDate: {date}")
            output_buffer.append("=" * 50)

            if 'Groups' in time_data and time_data['Groups']:
                # Create data structure for this date
                region_services = defaultdict(lambda: defaultdict(float))

                # Process groups
                for group in time_data['Groups']:
                    region, service = group['Keys']
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    currency = group['Metrics']['UnblendedCost']['Unit']

                    region_services[region][service] = cost
                    all_data[date][region][service] = cost

                # Add the results for this date to the buffer
                for region in sorted(region_services.keys()):
                    output_buffer.append(f"\nRegion: {region}")
                    output_buffer.append("-" * 40)

                    # Create a DataFrame for this region's services
                    services_df = pd.DataFrame({
                        'Service': list(region_services[region].keys()),
                        'Cost': list(region_services[region].values())
                    })

                    # Sort by cost descending
                    services_df = services_df.sort_values('Cost', ascending=False)

                    # Get top services by cost
                    top_services = services_df.head(5)

                    # Add region's services table to buffer
                    output_buffer.append(
                        tabulate(top_services.round(2), headers='keys', tablefmt='pretty', showindex=False))

                    # If there are more services, indicate the total for other services
                    if len(services_df) > 5:
                        other_cost = services_df.iloc[5:]['Cost'].sum()
                        output_buffer.append(
                            f"... and {len(services_df) - 5} more services totaling {other_cost:.2f} {currency}")

            else:
                output_buffer.append("No data found for this date")

            output_buffer.append("\n" + "-" * 75)

        # Convert all_data (defaultdict) to list of dicts
        breakdown_list = []
        for date, regions in all_data.items():
            for region, services in regions.items():
                for service, cost in services.items():
                    breakdown_list.append({
                        "date": date,
                        "region": region,
                        "service": service,
                        "cost": round(cost, 2)
                    })

        return {
            "status": "success",
            "breakdown_count": len(breakdown_list),
            "breakdown": breakdown_list
        }

    except Exception as e:
        error_message = f"Error retrieving detailed breakdown: {str(e)}"
        return {"status": "error", "message": error_message}

@mcp_server.tool()
def read_documentation(
        url: str,
        max_length: int = 5000,
        start_index: int = 0,
) -> str:
    """
    AWS 문서 페이지를 마크다운 형식으로 가져와 변환합니다.

    Args:
        url: 읽을 AWS 문서 페이지의 URL
        max_length: 반환할 최대 문자 수
        start_index: 이전 가져오기가 잘렸던 경우 더 많은 내용이 필요할 때 유용한, 이 문자 인덱스부터 반환 출력
    """
    # URL 유효성 검사
    url_str = str(url)
    if not re.match(r'^https?://docs\.aws\.amazon\.com/', url_str):
        return f'Invalid URL: {url_str}. URL must be from the docs.aws.amazon.com domain'

    try:
        # requests를 사용하여 문서 페이지 가져오기
        import requests
        response = requests.get(
            url_str,
            headers={'User-Agent': DEFAULT_USER_AGENT},
            timeout=30
        )
        response.raise_for_status()

        page_raw = response.text
        content_type = response.headers.get('content-type', '')

        # HTML 콘텐츠인지 확인하고 처리
        if is_html_content(page_raw, content_type):
            content = extract_content_from_html(page_raw)
        else:
            content = page_raw

        # 결과 포맷팅
        result = format_documentation_result(url_str, content, start_index, max_length)
        return result

    except Exception as e:
        error_msg = f'Failed to fetch {url_str}: {str(e)}'
        return error_msg


@mcp_server.tool()
def search_documentation(
        search_phrase: str,
        limit: int = 10
) -> List[Dict[str, Any]]:
    """
    공식 AWS 문서 검색 API를 사용하여 AWS 문서를 검색합니다.

    Args:
        search_phrase: 검색어
        limit: 반환할 최대 결과 수
    """
    try:
        # 검색 요청 페이로드 구성
        request_body = {
            'textQuery': {
                'input': search_phrase,
            },
            'contextAttributes': [{'key': 'domain', 'value': 'docs.aws.amazon.com'}],
            'acceptSuggestionBody': 'RawText',
            'locales': ['en_us'],
        }

        # HTTP 요청 보내기
        import requests
        response = requests.post(
            SEARCH_API_URL,
            json=request_body,
            headers={'Content-Type': 'application/json', 'User-Agent': DEFAULT_USER_AGENT},
            timeout=30
        )
        response.raise_for_status()

        # 응답 파싱
        data = response.json()

        results = []
        if 'suggestions' in data:
            for i, suggestion in enumerate(data['suggestions'][:limit]):
                if 'textExcerptSuggestion' in suggestion:
                    text_suggestion = suggestion['textExcerptSuggestion']
                    context = None

                    # 컨텍스트가 있는 경우 추가
                    if 'summary' in text_suggestion:
                        context = text_suggestion['summary']
                    elif 'suggestionBody' in text_suggestion:
                        context = text_suggestion['suggestionBody']

                    results.append({
                        'rank_order': i + 1,
                        'url': text_suggestion.get('link', ''),
                        'title': text_suggestion.get('title', ''),
                        'context': context
                    })

        return results

    except Exception as e:
        error_msg = f'Error searching AWS docs: {str(e)}'
        return [{'rank_order': 1, 'url': '', 'title': error_msg, 'context': None}]


@mcp_server.tool()
def recommend_documentation(
        url: str
) -> List[Dict[str, Any]]:
    """
    AWS 문서 페이지에 대한 콘텐츠 추천을 가져옵니다.

    Args:
        url: 추천을 받을 AWS 문서 페이지의 URL
    """
    try:
        url_str = str(url)
        recommendation_url = f'{RECOMMENDATIONS_API_URL}?path={url_str}'

        # HTTP 요청 보내기
        import requests
        response = requests.get(
            recommendation_url,
            headers={'User-Agent': DEFAULT_USER_AGENT},
            timeout=30
        )
        response.raise_for_status()

        # 응답 파싱
        data = response.json()

        # 결과 파싱
        results = parse_recommendation_results(data)
        return results

    except Exception as e:
        error_msg = f'Error getting recommendations: {str(e)}'
        return [{'url': '', 'title': error_msg, 'context': None}]


@mcp_server.tool()
def generate_architecture_diagram(
        code: str,
        filename: str = None,
        timeout: int = 30
) -> Dict[str, Any]:
    """
    Generate an architecture diagram from Python code using the diagrams package.

    This tool accepts Python code that uses the diagrams package DSL and generates
    a PNG diagram, then uploads it to S3 and returns a presigned URL.

    Args:
        code: Python code string using the diagrams package DSL
        filename: Optional output filename (without extension)
        timeout: Timeout in seconds for diagram generation

    Returns:
        Dictionary with the S3 URL and status information
    """
    try:
        result = generate_diagram(code, filename, timeout)
        # DiagramGenerateResponse 객체를 딕셔너리로 변환
        return {
            'status': result.status,
            'url': result.url,
            's3_key': result.s3_key,
            'message': result.message
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error generating diagram: {str(e)}'
        }


@mcp_server.tool()
def get_diagram_code_examples(
        diagram_type: str = "all"
) -> Dict[str, Any]:
    """
    Get example code for different types of architecture diagrams.

    This tool provides ready-to-use example code for various diagram types.
    Use these examples to understand the syntax and capabilities of the diagrams package.

    Args:
        diagram_type: Type of diagram example to return (aws, sequence, flow, class, k8s, onprem, custom, all)

    Returns:
        Dictionary with example code for the requested diagram type(s)
    """
    try:
        # Convert string to DiagramType enum
        if diagram_type.lower() == "aws":
            dtype = DiagramType.AWS
        elif diagram_type.lower() == "k8s":
            dtype = DiagramType.K8S
        elif diagram_type.lower() == "flow":
            dtype = DiagramType.FLOW
        elif diagram_type.lower() == "sequence":
            dtype = DiagramType.SEQUENCE
        elif diagram_type.lower() == "class":
            dtype = DiagramType.CLASS
        elif diagram_type.lower() == "onprem":
            dtype = DiagramType.ONPREM
        elif diagram_type.lower() == "custom":
            dtype = DiagramType.CUSTOM
        else:
            dtype = DiagramType.ALL

        result = get_diagram_examples(dtype)
        # DiagramExampleResponse 객체를 딕셔너리로 변환
        return {
            'examples': result.examples
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error getting examples: {str(e)}'
        }


@mcp_server.tool()
def list_available_diagram_icons(
        provider_filter: str = None,
        service_filter: str = None
) -> Dict[str, Any]:
    """
    List available icons from the diagrams package with optional filtering.

    This tool helps you discover what icons are available for creating diagrams.
    Call without filters to see all providers, or use filters to narrow down results.

    Args:
        provider_filter: Filter icons by provider name (e.g., "aws", "gcp", "k8s")
        service_filter: Filter icons by service name (e.g., "compute", "database", "network")

    Returns:
        Dictionary with available providers, services, and icons
    """
    try:
        result = list_diagram_icons(provider_filter, service_filter)
        # DiagramIconsResponse 객체를 딕셔너리로 변환
        return {
            'providers': result.providers,
            'filtered': result.filtered,
            'filter_info': result.filter_info
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error listing icons: {str(e)}'
        }


@mcp_server.tool()
def generate_line_chart(
        data: str,
        width: int = 600,
        height: int = 400,
        title: str = "",
        axis_x_title: str = "",
        axis_y_title: str = "",
        stack: bool = False
) -> Dict[str, Any]:
    """
    Generate a line chart to show trends over time.

    Args:
        data: JSON string of data for line chart, such as '[{"time": "2015", "value": 23}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart
        axis_x_title: X-axis title
        axis_y_title: Y-axis title
        stack: Whether stacking is enabled for multi-series data

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        if not validate_chart_data(chart_data, ["time", "value"]):
            return {
                "status": "error",
                "message": "Invalid data format. Each item must have 'time' and 'value' fields."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height,
            "title": title,
            "axisXTitle": axis_x_title,
            "axisYTitle": axis_y_title,
            "stack": stack
        }

        result = generate_chart_url("line", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating line chart: {str(e)}"
        }


@mcp_server.tool()
def generate_bar_chart(
        data: str,
        width: int = 600,
        height: int = 400,
        title: str = "",
        axis_x_title: str = "",
        axis_y_title: str = "",
        group: bool = False,
        stack: bool = True
) -> Dict[str, Any]:
    """
    Generate a bar chart for numerical comparisons among different categories.

    Args:
        data: JSON string of data for bar chart, such as '[{"category": "Category A", "value": 10}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart
        axis_x_title: X-axis title
        axis_y_title: Y-axis title
        group: Whether grouping is enabled (requires 'group' field in data)
        stack: Whether stacking is enabled (requires 'group' field in data)

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        if not validate_chart_data(chart_data, ["category", "value"]):
            return {
                "status": "error",
                "message": "Invalid data format. Each item must have 'category' and 'value' fields."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height,
            "title": title,
            "axisXTitle": axis_x_title,
            "axisYTitle": axis_y_title,
            "group": group,
            "stack": stack
        }

        result = generate_chart_url("bar", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating bar chart: {str(e)}"
        }


@mcp_server.tool()
def generate_pie_chart(
        data: str,
        width: int = 600,
        height: int = 400,
        title: str = "",
        inner_radius: float = 0.0
) -> Dict[str, Any]:
    """
    Generate a pie chart to show the proportion of parts.

    Args:
        data: JSON string of data for pie chart, such as '[{"category": "Category A", "value": 27}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart
        inner_radius: Inner radius for donut chart (0-1, default: 0)

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        if not validate_chart_data(chart_data, ["category", "value"]):
            return {
                "status": "error",
                "message": "Invalid data format. Each item must have 'category' and 'value' fields."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height,
            "title": title,
            "innerRadius": inner_radius
        }

        result = generate_chart_url("pie", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating pie chart: {str(e)}"
        }


@mcp_server.tool()
def generate_scatter_chart(
        data: str,
        width: int = 600,
        height: int = 400,
        title: str = "",
        axis_x_title: str = "",
        axis_y_title: str = ""
) -> Dict[str, Any]:
    """
    Generate a scatter chart to show the relationship between two variables.

    Args:
        data: JSON string of data for scatter chart, such as '[{"x": 10, "y": 15}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart
        axis_x_title: X-axis title
        axis_y_title: Y-axis title

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        if not validate_chart_data(chart_data, ["x", "y"]):
            return {
                "status": "error",
                "message": "Invalid data format. Each item must have 'x' and 'y' fields."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height,
            "title": title,
            "axisXTitle": axis_x_title,
            "axisYTitle": axis_y_title
        }

        result = generate_chart_url("scatter", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating scatter chart: {str(e)}"
        }


@mcp_server.tool()
def generate_area_chart(
        data: str,
        width: int = 600,
        height: int = 400,
        title: str = "",
        axis_x_title: str = "",
        axis_y_title: str = "",
        stack: bool = False
) -> Dict[str, Any]:
    """
    Generate an area chart to show data trends under continuous independent variables.

    Args:
        data: JSON string of data for area chart, such as '[{"time": "2018", "value": 99.9}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart
        axis_x_title: X-axis title
        axis_y_title: Y-axis title
        stack: Whether stacking is enabled (requires 'group' field in data)

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        if not validate_chart_data(chart_data, ["time", "value"]):
            return {
                "status": "error",
                "message": "Invalid data format. Each item must have 'time' and 'value' fields."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height,
            "title": title,
            "axisXTitle": axis_x_title,
            "axisYTitle": axis_y_title,
            "stack": stack
        }

        result = generate_chart_url("area", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating area chart: {str(e)}"
        }


@mcp_server.tool()
def generate_word_cloud_chart(
        data: str,
        width: int = 600,
        height: int = 400,
        title: str = ""
) -> Dict[str, Any]:
    """
    Generate a word cloud chart to show word frequency through text size variation.

    Args:
        data: JSON string of data for word cloud, such as '[{"text": "word", "value": 4.272}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        if not validate_chart_data(chart_data, ["text", "value"]):
            return {
                "status": "error",
                "message": "Invalid data format. Each item must have 'text' and 'value' fields."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height,
            "title": title
        }

        result = generate_chart_url("word-cloud", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating word cloud chart: {str(e)}"
        }


@mcp_server.tool()
def generate_radar_chart(
        data: str,
        width: int = 600,
        height: int = 400,
        title: str = ""
) -> Dict[str, Any]:
    """
    Generate a radar chart to display multidimensional data (four dimensions or more).

    Args:
        data: JSON string of data for radar chart, such as '[{"name": "Design", "value": 70}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        if not validate_chart_data(chart_data, ["name", "value"]):
            return {
                "status": "error",
                "message": "Invalid data format. Each item must have 'name' and 'value' fields."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height,
            "title": title
        }

        result = generate_chart_url("radar", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating radar chart: {str(e)}"
        }


@mcp_server.tool()
def generate_column_chart(
        data: str,
        width: int = 600,
        height: int = 400,
        title: str = "",
        axis_x_title: str = "",
        axis_y_title: str = "",
        group: bool = True,
        stack: bool = False
) -> Dict[str, Any]:
    """
    Generate a column chart for comparing categorical data.

    Args:
        data: JSON string of data for column chart, such as '[{"category": "Beijing", "value": 825, "group": "Gas Car"}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart
        axis_x_title: X-axis title
        axis_y_title: Y-axis title
        group: Whether grouping is enabled (requires 'group' field in data)
        stack: Whether stacking is enabled (requires 'group' field in data)

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        if not validate_chart_data(chart_data, ["category", "value"]):
            return {
                "status": "error",
                "message": "Invalid data format. Each item must have 'category' and 'value' fields."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height,
            "title": title,
            "axisXTitle": axis_x_title,
            "axisYTitle": axis_y_title,
            "group": group,
            "stack": stack
        }

        result = generate_chart_url("column", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating column chart: {str(e)}"
        }


@mcp_server.tool()
def generate_histogram_chart(
        data: str,
        width: int = 600,
        height: int = 400,
        title: str = "",
        axis_x_title: str = "",
        axis_y_title: str = "",
        bin_number: int = None
) -> Dict[str, Any]:
    """
    Generate a histogram chart to show frequency distribution of data.

    Args:
        data: JSON string of numeric data, such as '[78, 88, 60, 100, 95]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart
        axis_x_title: X-axis title
        axis_y_title: Y-axis title
        bin_number: Number of bins for histogram (optional)

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        # Validate that data is a list of numbers
        if not isinstance(chart_data, list) or not all(isinstance(x, (int, float)) for x in chart_data):
            return {
                "status": "error",
                "message": "Invalid data format. Data must be a list of numbers."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height,
            "title": title,
            "axisXTitle": axis_x_title,
            "axisYTitle": axis_y_title
        }

        if bin_number is not None:
            options["binNumber"] = bin_number

        result = generate_chart_url("histogram", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating histogram: {str(e)}"
        }


@mcp_server.tool()
def generate_treemap_chart(
        data: str,
        width: int = 600,
        height: int = 400,
        title: str = ""
) -> Dict[str, Any]:
    """
    Generate a treemap chart to display hierarchical data.

    Args:
        data: JSON string of hierarchical data, such as '[{"name": "Design", "value": 70, "children": [{"name": "Tech", "value": 20}]}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        # Basic validation for treemap data structure
        if not isinstance(chart_data, list):
            return {
                "status": "error",
                "message": "Invalid data format. Data must be a list of tree nodes."
            }

        for item in chart_data:
            if not isinstance(item, dict) or "name" not in item or "value" not in item:
                return {
                    "status": "error",
                    "message": "Invalid data format. Each item must have 'name' and 'value' fields."
                }

        options = {
            "data": chart_data,
            "width": width,
            "height": height,
            "title": title
        }

        result = generate_chart_url("treemap", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating treemap: {str(e)}"
        }


@mcp_server.tool()
def generate_dual_axes_chart(
        categories: str,
        series: str,
        width: int = 600,
        height: int = 400,
        title: str = "",
        axis_x_title: str = ""
) -> Dict[str, Any]:
    """
    Generate a dual axes chart combining bar and line charts.

    Args:
        categories: JSON string of categories, such as '["2015", "2016", "2017"]'
        series: JSON string of series data, such as '[{"type": "column", "data": [91.9, 99.1, 101.6], "axisYTitle": "Sales"}, {"type": "line", "data": [0.055, 0.06, 0.062], "axisYTitle": "Ratio"}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)
        title: Title of the chart
        axis_x_title: X-axis title

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        categories_data = json.loads(categories)
        series_data = json.loads(series)

        if not isinstance(categories_data, list) or not categories_data:
            return {
                "status": "error",
                "message": "Categories must be a non-empty list."
            }

        if not isinstance(series_data, list) or not series_data:
            return {
                "status": "error",
                "message": "Series must be a non-empty list."
            }

        # Validate series data structure
        for series_item in series_data:
            if not isinstance(series_item, dict) or "type" not in series_item or "data" not in series_item:
                return {
                    "status": "error",
                    "message": "Each series item must have 'type' and 'data' fields."
                }

            if series_item["type"] not in ["column", "line"]:
                return {
                    "status": "error",
                    "message": "Series type must be 'column' or 'line'."
                }

        options = {
            "categories": categories_data,
            "series": series_data,
            "width": width,
            "height": height,
            "title": title,
            "axisXTitle": axis_x_title
        }

        result = generate_chart_url("dual-axes", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for categories or series parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating dual axes chart: {str(e)}"
        }


@mcp_server.tool()
def generate_mind_map(
        data: str,
        width: int = 600,
        height: int = 400
) -> Dict[str, Any]:
    """
    Generate a mind map chart to organize hierarchical information.

    Args:
        data: JSON string of mind map data, such as '{"name": "main topic", "children": [{"name": "topic 1", "children": [{"name": "subtopic 1-1"}]}]}'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        # Validate mind map data structure
        if not isinstance(chart_data, dict) or "name" not in chart_data:
            return {
                "status": "error",
                "message": "Invalid data format. Root node must have a 'name' field."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height
        }

        result = generate_chart_url("mind-map", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating mind map: {str(e)}"
        }


@mcp_server.tool()
def generate_network_graph(
        nodes: str,
        edges: str,
        width: int = 600,
        height: int = 400
) -> Dict[str, Any]:
    """
    Generate a network graph to show relationships between entities.

    Args:
        nodes: JSON string of nodes, such as '[{"name": "node1"}, {"name": "node2"}]'
        edges: JSON string of edges, such as '[{"source": "node1", "target": "node2", "name": "edge1"}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        nodes_data = json.loads(nodes)
        edges_data = json.loads(edges)

        # Validate nodes data
        if not isinstance(nodes_data, list) or not nodes_data:
            return {
                "status": "error",
                "message": "Nodes must be a non-empty list."
            }

        for node in nodes_data:
            if not isinstance(node, dict) or "name" not in node:
                return {
                    "status": "error",
                    "message": "Each node must have a 'name' field."
                }

        # Validate edges data
        if not isinstance(edges_data, list):
            return {
                "status": "error",
                "message": "Edges must be a list."
            }

        for edge in edges_data:
            if not isinstance(edge, dict) or "source" not in edge or "target" not in edge:
                return {
                    "status": "error",
                    "message": "Each edge must have 'source' and 'target' fields."
                }

        chart_data = {
            "nodes": nodes_data,
            "edges": edges_data
        }

        options = {
            "data": chart_data,
            "width": width,
            "height": height
        }

        result = generate_chart_url("network-graph", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for nodes or edges parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating network graph: {str(e)}"
        }


@mcp_server.tool()
def generate_flow_diagram(
        nodes: str,
        edges: str,
        width: int = 600,
        height: int = 400
) -> Dict[str, Any]:
    """
    Generate a flow diagram to show process steps and decision points.

    Args:
        nodes: JSON string of nodes, such as '[{"name": "Start"}, {"name": "Process"}]'
        edges: JSON string of edges, such as '[{"source": "Start", "target": "Process", "name": "flow"}]'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        nodes_data = json.loads(nodes)
        edges_data = json.loads(edges)

        # Validate nodes data
        if not isinstance(nodes_data, list) or not nodes_data:
            return {
                "status": "error",
                "message": "Nodes must be a non-empty list."
            }

        for node in nodes_data:
            if not isinstance(node, dict) or "name" not in node:
                return {
                    "status": "error",
                    "message": "Each node must have a 'name' field."
                }

        # Validate edges data
        if not isinstance(edges_data, list):
            return {
                "status": "error",
                "message": "Edges must be a list."
            }

        for edge in edges_data:
            if not isinstance(edge, dict) or "source" not in edge or "target" not in edge:
                return {
                    "status": "error",
                    "message": "Each edge must have 'source' and 'target' fields."
                }

        chart_data = {
            "nodes": nodes_data,
            "edges": edges_data
        }

        options = {
            "data": chart_data,
            "width": width,
            "height": height
        }

        result = generate_chart_url("flow-diagram", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for nodes or edges parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating flow diagram: {str(e)}"
        }


@mcp_server.tool()
def generate_fishbone_diagram(
        data: str,
        width: int = 600,
        height: int = 400
) -> Dict[str, Any]:
    """
    Generate a fishbone diagram to analyze causes and effects.

    Args:
        data: JSON string of fishbone data, such as '{"name": "main problem", "children": [{"name": "cause 1", "children": [{"name": "subcause 1-1"}]}]}'
        width: Width of the chart (default: 600)
        height: Height of the chart (default: 400)

    Returns:
        Dictionary with chart URL or error message
    """
    try:
        chart_data = json.loads(data)

        # Validate fishbone data structure
        if not isinstance(chart_data, dict) or "name" not in chart_data:
            return {
                "status": "error",
                "message": "Invalid data format. Root node must have a 'name' field."
            }

        options = {
            "data": chart_data,
            "width": width,
            "height": height
        }

        result = generate_chart_url("fishbone-diagram", options)
        return result

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON format for data parameter"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating fishbone diagram: {str(e)}"
        }
# Define the lambda handler
def lambda_handler(event, context):
    """AWS Lambda handler function."""
    return mcp_server.handle_request(event, context)