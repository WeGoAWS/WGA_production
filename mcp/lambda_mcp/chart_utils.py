"""
Chart utility functions for generating various types of charts.
"""

import os
import requests
from typing import Dict, List, Any

# Chart server configuration
DEFAULT_CHART_SERVER = "https://antv-studio.alipay.com/api/gpt-vis"


def generate_chart_url(chart_type: str, options: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    """Generate a chart URL using the provided configuration."""
    try:
        url = os.environ.get('VIS_REQUEST_SERVER', DEFAULT_CHART_SERVER)

        payload = {
            "type": chart_type,
            "source": "lambda-mcp-server-chart",
            **options
        }

        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )
        response.raise_for_status()

        result_data = response.json()
        chart_url = result_data.get("resultObj")

        if chart_url:
            return {
                "status": "success",
                "url": chart_url,
                "chart_type": chart_type,
                "message": f"Chart generated successfully: {chart_type}"
            }
        else:
            return {
                "status": "error",
                "chart_type": chart_type,
                "message": "No chart URL returned from server"
            }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "chart_type": chart_type,
            "message": "Request timeout while generating chart"
        }
    except requests.exceptions.HTTPError as e:
        return {
            "status": "error",
            "chart_type": chart_type,
            "message": f"HTTP error {e.response.status_code}: {e.response.text}"
        }
    except Exception as e:
        return {
            "status": "error",
            "chart_type": chart_type,
            "message": f"Error generating chart: {str(e)}"
        }


def validate_chart_data(data: List[Dict], required_fields: List[str]) -> bool:
    """Validate that chart data contains required fields."""
    if not data:
        return False

    for item in data:
        if not all(field in item for field in required_fields):
            return False

    return True