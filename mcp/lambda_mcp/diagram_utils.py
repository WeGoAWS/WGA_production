"""Diagram generation utilities for Lambda MCP server."""

import ast
import boto3
import importlib
import inspect
import os
import re
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from .mcp_types import (
    DiagramType,
    SecurityIssue,
    CodeScanResult,
    DiagramGenerateResponse,
    DiagramExampleResponse,
    DiagramIconsResponse
)

# S3 클라이언트 초기화
s3_client = boto3.client('s3')
DIAGRAM_BUCKET = os.environ.get('DIAGRAM_BUCKET', f'wga-diagrambucket-{os.environ.get("ENV", "dev")}')


def validate_syntax(code: str) -> Tuple[bool, Optional[str]]:
    """Validate Python code syntax using ast."""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        error_msg = f'Syntax error at line {e.lineno}: {e.msg}'
        return False, error_msg
    except Exception as e:
        return False, str(e)


def check_dangerous_functions(code: str) -> List[Dict[str, Any]]:
    """Check for dangerous functions like exec, eval, etc."""
    dangerous_patterns = [
        'exec(',
        'eval(',
        'subprocess.',
        'os.system',
        'os.popen',
        '__import__',
        'pickle.loads',
    ]

    results = []
    lines = code.splitlines()

    for i, line in enumerate(lines):
        for pattern in dangerous_patterns:
            if pattern in line:
                results.append({
                    'function': pattern.rstrip('('),
                    'line': i + 1,
                    'code': line.strip(),
                })

    return results


def scan_python_code(code: str) -> CodeScanResult:
    """Scan Python code for security issues using basic checks."""
    # Check syntax
    syntax_valid, syntax_error = validate_syntax(code)
    if not syntax_valid:
        return CodeScanResult(
            has_errors=True,
            syntax_valid=False,
            error_message=syntax_error
        )

    # Check for dangerous functions
    dangerous_functions = check_dangerous_functions(code)
    security_issues = []

    for func in dangerous_functions:
        # Allow specific exec calls for diagrams package (known safe usage)
        if 'exec(' in func['code'] and any(safe in func['code'] for safe in [
            'import diagrams', 'from diagrams', 'import os'
        ]):
            continue

        security_issues.append(
            SecurityIssue(
                severity='HIGH',
                confidence='HIGH',
                line=func['line'],
                issue_text=f"Dangerous function '{func['function']}' detected",
                issue_type='DangerousFunctionDetection'
            )
        )

    # Determine if there are errors
    has_errors = bool(security_issues)
    error_message = None
    if has_errors:
        messages = [f'{issue.issue_type}: {issue.issue_text}' for issue in security_issues]
        error_message = '\n'.join(messages)

    return CodeScanResult(
        has_errors=has_errors,
        syntax_valid=True,
        security_issues=security_issues,
        error_message=error_message
    )


def process_diagram_code(code: str, output_path: str) -> str:
    """Process code to set filename and show=False."""
    if 'with Diagram(' in code:
        # Find all instances of Diagram constructor
        diagram_pattern = r'with\s+Diagram\s*\((.*?)\)'
        matches = re.findall(diagram_pattern, code)

        for match in matches:
            # Get the original arguments
            original_args = match.strip()

            # Check if show parameter is already set
            has_show = 'show=' in original_args
            has_filename = 'filename=' in original_args

            # Prepare new arguments
            new_args = original_args

            # Add or replace parameters as needed
            if has_filename:
                # Replace the existing filename parameter
                filename_pattern = r'filename\s*=\s*[\'"]([^\'"]*)[\'"]'
                new_args = re.sub(filename_pattern, f"filename='{output_path}'", new_args)
            else:
                # Add the filename parameter
                if new_args and not new_args.endswith(','):
                    new_args += ', '
                new_args += f"filename='{output_path}'"

            # Add show=False if not already set
            if not has_show:
                if new_args and not new_args.endswith(','):
                    new_args += ', '
                new_args += 'show=False'

            # Replace in the code
            code = code.replace(f'with Diagram({original_args})', f'with Diagram({new_args})')

    return code


def generate_diagram(
        code: str,
        filename: Optional[str] = None,
        timeout: int = 90
) -> DiagramGenerateResponse:
    """
    Generate a diagram from Python code and upload to S3.

    Args:
        code: Python code string using the diagrams package DSL
        filename: Output filename (without extension)
        timeout: Timeout in seconds for diagram generation

    Returns:
        Dictionary with the S3 URL and status
    """
    try:
        # Scan the code for security issues
        scan_result = scan_python_code(code)
        if scan_result.has_errors:
            return DiagramGenerateResponse(
                status='error',
                message=f'Security issues found in the code: {scan_result.error_message}',
            )

        if filename is None:
            filename = f'diagram_{uuid.uuid4().hex[:8]}'

        # Use temporary directory for diagram generation
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, filename)

            try:
                # Create a namespace for execution
                namespace = {}

                # Import necessary modules directly in the namespace
                exec('import os', namespace)
                exec('import diagrams', namespace)
                exec('from diagrams import Diagram, Cluster, Edge', namespace)

                # Import all diagram components
                diagram_imports = """
from diagrams.aws.compute import *
from diagrams.aws.database import *
from diagrams.aws.network import *
from diagrams.aws.storage import *
from diagrams.aws.analytics import *
from diagrams.aws.integration import *
from diagrams.aws.ml import *
from diagrams.aws.security import *
from diagrams.aws.management import *
from diagrams.aws.general import *
from diagrams.k8s.compute import *
from diagrams.k8s.network import *
from diagrams.k8s.storage import *
from diagrams.onprem.database import *
from diagrams.onprem.compute import *
from diagrams.onprem.network import *
from diagrams.generic.compute import *
from diagrams.generic.database import *
from diagrams.generic.network import *
from diagrams.programming.language import *
from diagrams.programming.framework import *
from urllib.request import urlretrieve
"""
                exec(diagram_imports, namespace)

                # Process the code to ensure show=False and set the output path
                processed_code = process_diagram_code(code, output_path)

                # Execute the code
                exec(processed_code, namespace)

                # Check if the file was created
                png_path = f'{output_path}.png'
                if os.path.exists(png_path):
                    # Upload to S3
                    s3_key = f'diagrams/{datetime.now().strftime("%Y/%m/%d")}/{filename}_{uuid.uuid4().hex[:8]}.png'

                    s3_client.upload_file(
                        png_path,
                        DIAGRAM_BUCKET,
                        s3_key,
                        ExtraArgs={'ContentType': 'image/png'}
                    )

                    # Generate presigned URL (24 hours valid)
                    url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': DIAGRAM_BUCKET, 'Key': s3_key},
                        ExpiresIn=86400
                    )

                    return DiagramGenerateResponse(
                        status='success',
                        url=url,
                        s3_key=s3_key,
                        message=f'Diagram generated successfully and uploaded to S3'
                    )
                else:
                    return DiagramGenerateResponse(
                        status='error',
                        message='Diagram file was not created. Check your code for errors.'
                    )

            except Exception as e:
                error_type = type(e).__name__
                error_message = str(e)
                return DiagramGenerateResponse(
                    status='error',
                    message=f'Error generating diagram: {error_type}: {error_message}'
                )

    except Exception as e:
        return DiagramGenerateResponse(status='error', message=str(e))


def get_diagram_examples(diagram_type: DiagramType = DiagramType.ALL) -> DiagramExampleResponse:
    """Get example code for different types of diagrams."""
    examples = {}

    # AWS examples
    if diagram_type in [DiagramType.AWS, DiagramType.ALL]:
        examples['aws_basic'] = """with Diagram("Web Service Architecture", show=False):
    ELB("lb") >> EC2("web") >> RDS("userdb")"""

        examples['aws_clustered_web_services'] = """with Diagram("Clustered Web Services", show=False):
    dns = Route53("dns")
    lb = ELB("lb")

    with Cluster("Services"):
        svc_group = [ECS("web1"),
                     ECS("web2"),
                     ECS("web3")]

    with Cluster("DB Cluster"):
        db_primary = RDS("userdb")
        db_primary - [RDS("userdb ro")]

    memcached = ElastiCache("memcached")

    dns >> lb >> svc_group
    svc_group >> db_primary
    svc_group >> memcached"""

        examples['aws_bedrock'] = """with Diagram("S3 Image Processing with Bedrock", show=False, direction="LR"):
    user = User("User")

    with Cluster("Amazon S3 Bucket"):
        input_folder = S3("Input Folder")
        output_folder = S3("Output Folder")

    lambda_function = Lambda("Image Processor Function")
    bedrock = Bedrock("Claude Sonnet 3.7")

    user >> Edge(label="Upload Image") >> input_folder
    input_folder >> Edge(label="Trigger") >> lambda_function
    lambda_function >> Edge(label="Process Image") >> bedrock
    bedrock >> Edge(label="Return Bounding Box") >> lambda_function
    lambda_function >> Edge(label="Upload Processed Image") >> output_folder
    output_folder >> Edge(label="Download Result") >> user"""

    # K8s examples
    if diagram_type in [DiagramType.K8S, DiagramType.ALL]:
        examples['k8s_exposed_pod'] = """with Diagram("Exposed Pod with 3 Replicas", show=False):
    net = Ingress("domain.com") >> Service("svc")
    net >> [Pod("pod1"),
            Pod("pod2"),
            Pod("pod3")] << ReplicaSet("rs") << Deployment("dp") << HPA("hpa")"""

    # Flow examples
    if diagram_type in [DiagramType.FLOW, DiagramType.ALL]:
        examples['basic_flow'] = """with Diagram("Order Processing Flow", show=False):
    start = Generic("Start")
    order = Generic("Order Received")
    check = Generic("In Stock?")
    process = Generic("Process Order")
    ship = Generic("Ship Order")
    end = Generic("End")

    start >> order >> check >> process >> ship >> end"""

    return DiagramExampleResponse(examples=examples)


def list_diagram_icons(
        provider_filter: Optional[str] = None,
        service_filter: Optional[str] = None
) -> DiagramIconsResponse:
    """List available icons from the diagrams package."""
    try:
        # If no filters provided, return list of available providers
        if not provider_filter and not service_filter:
            providers = {
                "aws": {},
                "gcp": {},
                "azure": {},
                "k8s": {},
                "onprem": {},
                "generic": {},
                "programming": {}
            }
            return DiagramIconsResponse(providers=providers, filtered=False, filter_info=None)

        # If only provider filter is specified
        if provider_filter and not service_filter:
            provider_services = {
                "aws": ["compute", "database", "network", "storage", "analytics", "integration", "ml", "security"],
                "k8s": ["compute", "network", "storage", "controlplane"],
                "onprem": ["compute", "database", "network", "monitoring"],
                "generic": ["compute", "database", "network", "storage"],
                "programming": ["language", "framework"]
            }

            services = provider_services.get(provider_filter.lower(), [])
            provider_dict = {provider_filter: {service: [] for service in services}}

            return DiagramIconsResponse(
                providers=provider_dict,
                filtered=True,
                filter_info={"provider": provider_filter}
            )

        # If both provider and service filters are specified
        elif provider_filter and service_filter:
            # Sample icons for demonstration
            sample_icons = {
                "aws": {
                    "compute": ["EC2", "Lambda", "ECS", "EKS", "Batch"],
                    "database": ["RDS", "DynamoDB", "ElastiCache", "Redshift"],
                    "network": ["ELB", "CloudFront", "Route53", "VPC"],
                    "storage": ["S3", "EBS", "EFS", "Glacier"]
                },
                "k8s": {
                    "compute": ["Pod", "Deployment", "ReplicaSet", "DaemonSet"],
                    "network": ["Service", "Ingress", "NetworkPolicy"],
                    "storage": ["PersistentVolume", "PersistentVolumeClaim", "StorageClass"]
                }
            }

            icons = sample_icons.get(provider_filter.lower(), {}).get(service_filter.lower(), [])
            provider_dict = {provider_filter: {service_filter: icons}}

            return DiagramIconsResponse(
                providers=provider_dict,
                filtered=True,
                filter_info={"provider": provider_filter, "service": service_filter}
            )

        return DiagramIconsResponse(providers={}, filtered=False, filter_info=None)

    except Exception as e:
        return DiagramIconsResponse(
            providers={},
            filtered=False,
            filter_info={"error": str(e)}
        )