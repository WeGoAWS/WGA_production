import os
import json
import httpx
import asyncio
import traceback

from awslabs.aws_documentation_mcp_server.server import search_documentation
from mcp.server.fastmcp import Context

LAMBDA_RUNTIME_API = os.environ["AWS_LAMBDA_RUNTIME_API"]

async def handle_event(event):
    print("[DEBUG] Received event:", event)

    ctx = Context()
    input_text = event.get("input", {}).get("text", "")

    try:
        results = await search_documentation(
            ctx,
            search_phrase=input_text,
            limit=3,
        )

        print("[DEBUG] Search results:")
        for r in results:
            print(r)

        return {
            "result": [r.dict() for r in results],
        }

    except Exception as e:
        print("[ERROR] Exception in handle_event:")
        traceback.print_exc()
        raise

async def main():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                print("[DEBUG] Waiting for next Lambda event")
                res = await client.get(f"http://{LAMBDA_RUNTIME_API}/2018-06-01/runtime/invocation/next", timeout=None)
                request_id = res.headers["Lambda-Runtime-Aws-Request-Id"]
                event = res.json()
                print("[DEBUG] Received request ID:", request_id)
                print("[DEBUG] Raw event JSON:", event)

                try:
                    result = await handle_event(event)
                    response_url = f"http://{LAMBDA_RUNTIME_API}/2018-06-01/runtime/invocation/{request_id}/response"
                    await client.post(response_url, json=result)
                    print("[DEBUG] Successfully responded to", request_id)
                except Exception as e:
                    error_url = f"http://{LAMBDA_RUNTIME_API}/2018-06-01/runtime/invocation/{request_id}/error"
                    error_payload = {
                        "errorMessage": str(e),
                        "trace": traceback.format_exc()
                    }
                    await client.post(error_url, json=error_payload)
                    print("[ERROR] Failed to handle event:", error_payload)

            except Exception as outer:
                print("[FATAL ERROR] Failed to fetch next invocation or post result:")
                traceback.print_exc()
                await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
