import os
import json
import boto3
import pandas as pd
import httpx
import re
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

# Define the lambda handler
def lambda_handler(event, context):
    """AWS Lambda handler function."""
    return mcp_server.handle_request(event, context)