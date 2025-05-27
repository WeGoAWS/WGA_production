"""
CloudWatch Logs Insights utility functions for log analysis
"""
from typing import Dict, List, Any

def generate_insights_query(analysis_type: str) -> str:
    """분석 유형에 따라 Logs Insights 쿼리를 자동 생성합니다."""

    queries = {
        "errors": """
            fields @timestamp, @message
            | filter @message like /ERROR/ or @message like /Exception/ or @message like /error/
            | stats count() by bin(5m), @message
            | sort @timestamp desc
            | limit 10000
        """,

        "performance": """
            fields @timestamp, @duration, @requestId
            | filter @type = "REPORT"
            | stats avg(@duration), max(@duration), min(@duration) by bin(5m)
            | sort @timestamp desc
        """,

        "security": """
            fields @timestamp, @message, sourceIPAddress, userIdentity.type
            | filter @message like /FAILED/ or @message like /Denied/ or @message like /Unauthorized/
            | stats count() by sourceIPAddress, userIdentity.type
            | sort count desc
            | limit 100
        """,

        "traffic": """
            fields @timestamp, @message
            | stats count() by bin(5m)
            | sort @timestamp desc
        """,

        "login": """
            fields @timestamp, sourceIPAddress, userIdentity.type, userIdentity.userName, 
                   userIdentity.sessionContext.sessionIssuer.userName, eventName, errorCode, errorMessage
            | filter eventName = "ConsoleLogin"
            | stats count() by sourceIPAddress, userIdentity.userName, errorCode
            | sort count desc
            | limit 10000
        """,

        "custom": """
            fields @timestamp, @message
            | sort @timestamp desc
            | limit 10000
        """
    }

    return queries.get(analysis_type, queries["custom"]).strip()


def analyze_insights_results(
        results: List[Dict],
        analysis_type: str,
        field_names: set
) -> Dict[str, Any]:
    """Logs Insights 결과를 분석하여 인사이트를 생성합니다."""

    if not results:
        return {"summary": "분석할 데이터가 없습니다."}

    analysis = {
        "total_records": len(results),
        "field_names": list(field_names),
        "insights": []
    }

    if analysis_type == "errors":
        # 에러 패턴 분석
        error_patterns = {}
        for result in results:
            message = result.get('@message', '')
            # 간단한 에러 패턴 추출
            if 'ERROR' in message or 'Exception' in message:
                # 첫 번째 단어를 패턴으로 사용
                pattern = message.split()[:3] if message.split() else ['Unknown']
                pattern_key = ' '.join(pattern)
                error_patterns[pattern_key] = error_patterns.get(pattern_key, 0) + 1

        # 상위 에러 패턴
        top_errors = sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:5]
        analysis["insights"].append({
            "type": "top_error_patterns",
            "data": top_errors
        })

    elif analysis_type == "performance":
        # 성능 통계 분석
        durations = []
        for result in results:
            if '@duration' in result:
                try:
                    duration = float(result['@duration'])
                    durations.append(duration)
                except (ValueError, TypeError):
                    continue

        if durations:
            analysis["insights"].append({
                "type": "performance_stats",
                "data": {
                    "avg_duration": sum(durations) / len(durations),
                    "max_duration": max(durations),
                    "min_duration": min(durations),
                    "sample_count": len(durations)
                }
            })

    elif analysis_type == "security":
        # 보안 이벤트 분석
        ip_addresses = {}
        for result in results:
            ip = result.get('sourceIPAddress', 'Unknown')
            ip_addresses[ip] = ip_addresses.get(ip, 0) + 1

        # 상위 IP 주소
        top_ips = sorted(ip_addresses.items(), key=lambda x: x[1], reverse=True)[:10]
        analysis["insights"].append({
            "type": "top_source_ips",
            "data": top_ips
        })

    elif analysis_type == "login":
        # Console 로그인 분석
        login_stats = {}
        failed_logins = {}
        success_logins = {}
        ip_locations = {}

        for result in results:
            source_ip = result.get('sourceIPAddress', 'Unknown')
            username = result.get('userIdentity.userName', 'Unknown')
            error_code = result.get('errorCode', 'Success')
            count = int(result.get('count', 0))

            # 전체 로그인 통계
            key = f"{username}@{source_ip}"
            login_stats[key] = login_stats.get(key, 0) + count

            # 실패한 로그인 통계
            if error_code and error_code != 'Success':
                failed_key = f"{username}@{source_ip} ({error_code})"
                failed_logins[failed_key] = failed_logins.get(failed_key, 0) + count
            else:
                success_key = f"{username}@{source_ip}"
                success_logins[success_key] = success_logins.get(success_key, 0) + count

            # IP별 통계
            ip_locations[source_ip] = ip_locations.get(source_ip, 0) + count

        # 상위 로그인 시도
        top_logins = sorted(login_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        top_failed = sorted(failed_logins.items(), key=lambda x: x[1], reverse=True)[:10]
        top_success = sorted(success_logins.items(), key=lambda x: x[1], reverse=True)[:10]
        suspicious_ips = sorted(ip_locations.items(), key=lambda x: x[1], reverse=True)[:10]

        analysis["insights"].extend([
            {
                "type": "top_login_attempts",
                "description": "가장 많은 로그인 시도 (사용자@IP)",
                "data": top_logins
            },
            {
                "type": "failed_logins",
                "description": "실패한 로그인 시도",
                "data": top_failed
            },
            {
                "type": "successful_logins",
                "description": "성공한 로그인",
                "data": top_success
            },
            {
                "type": "suspicious_ips",
                "description": "의심스러운 IP 주소 (로그인 시도 횟수 기준)",
                "data": suspicious_ips
            }
        ])

    elif analysis_type == "traffic":
        # 트래픽 패턴 분석
        timestamps = []
        for result in results:
            if '@timestamp' in result:
                timestamps.append(result['@timestamp'])

        analysis["insights"].append({
            "type": "traffic_pattern",
            "data": {
                "total_events": len(timestamps),
                "time_span": f"{timestamps[0] if timestamps else 'N/A'} to {timestamps[-1] if timestamps else 'N/A'}"
            }
        })

    # 공통 분석: 시간대별 분포
    time_distribution = {}
    for result in results:
        timestamp = result.get('@timestamp', '')
        if timestamp:
            # 시간 추출 (예: 2024-01-01T10:30:00 -> 10시)
            try:
                hour = timestamp.split('T')[1][:2] if 'T' in timestamp else '00'
                time_distribution[f"{hour}:00"] = time_distribution.get(f"{hour}:00", 0) + 1
            except (IndexError, AttributeError):
                continue

    if time_distribution:
        analysis["insights"].append({
            "type": "hourly_distribution",
            "data": dict(sorted(time_distribution.items()))
        })

    return analysis


def get_query_templates() -> Dict[str, Any]:
    """
    CloudWatch Logs Insights에서 사용할 수 있는 쿼리 템플릿을 반환합니다.

    Returns:
        Dictionary with query templates for different analysis types
    """
    return {
        "error_analysis": """
            fields @timestamp, @message, @requestId
            | filter @message like /ERROR/ or @message like /Exception/ or @message like /FAILED/
            | stats count() by bin(5m)
            | sort @timestamp desc
        """,

        "performance_monitoring": """
            fields @timestamp, @duration, @billedDuration, @memorySize, @maxMemoryUsed
            | filter @type = "REPORT"
            | stats avg(@duration), max(@duration), min(@duration), avg(@maxMemoryUsed) by bin(5m)
            | sort @timestamp desc
        """,

        "api_gateway_analysis": """
            fields @timestamp, @message, ip, httpMethod, status, responseTime
            | filter status >= 400
            | stats count() by status, httpMethod
            | sort count desc
        """,

        "cloudtrail_security": """
            fields eventTime, sourceIPAddress, userIdentity.type, eventName, errorCode
            | filter errorCode exists or eventName like /Delete/ or eventName like /Terminate/
            | stats count() by sourceIPAddress, eventName
            | sort count desc
        """,

        "lambda_cold_starts": """
            fields @timestamp, @message, @requestId
            | filter @message like /INIT_START/
            | stats count() by bin(1h)
            | sort @timestamp desc
        """,

        "console_login_analysis": """
            fields @timestamp, sourceIPAddress, userIdentity.userName, userIdentity.type, 
                   errorCode, errorMessage, responseElements.ConsoleLogin
            | filter eventName = "ConsoleLogin"
            | sort @timestamp desc
        """,

        "failed_console_logins": """
            fields @timestamp, sourceIPAddress, userIdentity.userName, errorCode, errorMessage
            | filter eventName = "ConsoleLogin" and errorCode exists
            | stats count() by sourceIPAddress, userIdentity.userName, errorCode
            | sort count desc
        """,

        "successful_console_logins": """
            fields @timestamp, sourceIPAddress, userIdentity.userName, userAgent
            | filter eventName = "ConsoleLogin" and errorCode not exists
            | stats count() by sourceIPAddress, userIdentity.userName
            | sort count desc
        """,

        "custom_metric_extraction": """
            fields @timestamp, @message
            | parse @message /Metric: (?<metric_name>\\w+) = (?<metric_value>\\d+)/
            | stats avg(metric_value), max(metric_value) by metric_name, bin(5m)
            | sort @timestamp desc
        """,

        "suspicious_login_patterns": """
            fields @timestamp, sourceIPAddress, userIdentity.userName, errorCode
            | filter eventName = "ConsoleLogin"
            | stats count() by sourceIPAddress, bin(1h)
            | sort count desc
            | limit 100
        """
    }