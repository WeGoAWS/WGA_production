import sys
from mcp.client.stdio import StdioServerParameters
from mcp_lambda import stdio_server_adapter

server_params = StdioServerParameters(
    command=sys.executable,
    args=[
        "-m",
        "mcp_server_time",
        "--local-timezone",
        "America/New_York",
    ],
)


def handler(event, context):
    return stdio_server_adapter(server_params, event, context)