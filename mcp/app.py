import os
import json
import boto3
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict, List, Any
from tabulate import tabulate
from pydantic import BaseModel, Field
from lambda_mcp.lambda_mcp import LambdaMCPServer

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

class DaysParam(BaseModel):
    """Parameters for specifying the number of days to look back."""

    days: int = Field(
        default=7,
        description="Number of days to look back for cost data"
    )

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
            "apigateway": ["/aws/apigateway"],
            "cloudtrail": ["/aws/cloudtrail"],
            "s3": ["/aws/s3", "/aws/s3-access"],
            "vpc": ["/aws/vpc"],
            "waf": ["/aws/waf"],
            "bedrock": [f"/aws/bedrock/modelinvocations"],
            "iam": ["/aws/dummy-security-logs"]
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
async def get_detailed_breakdown_by_day(params: DaysParam) -> str:  # Dict[str, Any]:
    """
    Retrieve daily spend breakdown by region, service, and instance type.

    Args:
        params: Parameters specifying the number of days to look back

    Returns:
        Dict[str, Any]: A tuple containing:
            - A nested dictionary with cost data organized by date, region, and service
            - A string containing the formatted output report
        or (None, error_message) if an error occurs.
    """
    # Initialize the Cost Explorer client
    ce_client = boto3.client('ce')

    # Get the days parameter
    days = params.days

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

                    # For EC2, get instance type breakdown
                    if any(s.startswith('Amazon Elastic Compute') for s in region_services[region].keys()):
                        try:
                            instance_response = get_instance_type_breakdown(
                                ce_client,
                                date,
                                region,
                                'Amazon Elastic Compute Cloud - Compute',
                                'INSTANCE_TYPE'
                            )

                            if instance_response:
                                output_buffer.append("\n  EC2 Instance Type Breakdown:")
                                output_buffer.append("  " + "-" * 38)

                                # Get table with indentation
                                instance_table = tabulate(instance_response.round(2), headers='keys', tablefmt='pretty',
                                                          showindex=False)
                                for line in instance_table.split('\n'):
                                    output_buffer.append(f"  {line}")

                        except Exception as e:
                            output_buffer.append(f"  Note: Could not retrieve EC2 instance type breakdown: {str(e)}")

                    # For SageMaker, get instance type breakdown
                    if any(s == 'Amazon SageMaker' for s in region_services[region].keys()):
                        try:
                            sagemaker_instance_response = get_instance_type_breakdown(
                                ce_client,
                                date,
                                region,
                                'Amazon SageMaker',
                                'INSTANCE_TYPE'
                            )

                            if sagemaker_instance_response is not None and not sagemaker_instance_response.empty:
                                output_buffer.append("\n  SageMaker Instance Type Breakdown:")
                                output_buffer.append("  " + "-" * 38)

                                # Get table with indentation
                                sagemaker_table = tabulate(sagemaker_instance_response.round(2), headers='keys',
                                                           tablefmt='pretty', showindex=False)
                                for line in sagemaker_table.split('\n'):
                                    output_buffer.append(f"  {line}")

                            # Also try to get usage type breakdown for SageMaker (notebooks, endpoints, etc.)
                            sagemaker_usage_response = get_instance_type_breakdown(
                                ce_client,
                                date,
                                region,
                                'Amazon SageMaker',
                                'USAGE_TYPE'
                            )

                            if sagemaker_usage_response is not None and not sagemaker_usage_response.empty:
                                output_buffer.append("\n  SageMaker Usage Type Breakdown:")
                                output_buffer.append("  " + "-" * 38)

                                # Get table with indentation
                                usage_table = tabulate(sagemaker_usage_response.round(2), headers='keys',
                                                       tablefmt='pretty', showindex=False)
                                for line in usage_table.split('\n'):
                                    output_buffer.append(f"  {line}")

                        except Exception as e:
                            output_buffer.append(f"  Note: Could not retrieve SageMaker breakdown: {str(e)}")
            else:
                output_buffer.append("No data found for this date")

            output_buffer.append("\n" + "-" * 75)

        # Join the buffer into a single string
        formatted_output = "\n".join(output_buffer)

        # Return both the raw data and the formatted output
        # return {"data": all_data, "formatted_output": formatted_output}
        return formatted_output

    except Exception as e:
        error_message = f"Error retrieving detailed breakdown: {str(e)}"
        # return {"data": None, "formatted_output": error_message}
        return error_message


def get_instance_type_breakdown(ce_client, date, region, service, dimension_key):
    """
    Helper function to get instance type or usage type breakdown for a specific service.

    Args:
        ce_client: The Cost Explorer client
        date: The date to query
        region: The AWS region
        service: The AWS service name
        dimension_key: The dimension to group by (e.g., 'INSTANCE_TYPE' or 'USAGE_TYPE')

    Returns:
        DataFrame containing the breakdown or None if no data
    """
    tomorrow = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    instance_response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': date,
            'End': tomorrow
        },
        Granularity='DAILY',
        Filter={
            'And': [
                {
                    'Dimensions': {
                        'Key': 'REGION',
                        'Values': [region]
                    }
                },
                {
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': [service]
                    }
                }
            ]
        },
        Metrics=['UnblendedCost'],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': dimension_key
            }
        ]
    )

    if ('ResultsByTime' in instance_response and
            instance_response['ResultsByTime'] and
            'Groups' in instance_response['ResultsByTime'][0] and
            instance_response['ResultsByTime'][0]['Groups']):

        instance_data = instance_response['ResultsByTime'][0]
        instance_costs = []

        for instance_group in instance_data['Groups']:
            type_value = instance_group['Keys'][0]
            cost_value = float(instance_group['Metrics']['UnblendedCost']['Amount'])

            # Add a better label for the dimension used
            column_name = 'Instance Type' if dimension_key == 'INSTANCE_TYPE' else 'Usage Type'

            instance_costs.append({
                column_name: type_value,
                'Cost': cost_value
            })

        # Create DataFrame and sort by cost
        result_df = pd.DataFrame(instance_costs)
        if not result_df.empty:
            result_df = result_df.sort_values('Cost', ascending=False)
            return result_df

    return None

# Define the lambda handler
def lambda_handler(event, context):
    """AWS Lambda handler function."""
    return mcp_server.handle_request(event, context)