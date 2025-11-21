"""FastAPI SSE transport for RPG MCP Server."""
import sys
import json
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from config import Config
from mcp_bridge import bridge


# Add MCP server to Python path
mcp_src_path = Config.MCP_SERVER_PATH / "src"
sys.path.insert(0, str(mcp_src_path))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    print(f"Starting RPG MCP API on {Config.HOST}:{Config.PORT}")
    print(f"MCP Server path: {Config.MCP_SERVER_PATH}")
    yield
    print("Shutting down RPG MCP API")


app = FastAPI(
    title="RPG MCP API",
    description="FastAPI SSE transport for RPG MCP Server",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware - allow all origins since security is via IP whitelist
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (security via IP whitelist)
    allow_credentials=False,  # Can't use credentials with wildcard origin
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "RPG MCP API",
        "status": "running",
        "version": "0.1.0"
    }


@app.api_route("/mcp", methods=["GET", "POST", "OPTIONS", "HEAD"])
async def mcp_endpoint(request: Request):
    """
    Unified MCP endpoint supporting both GET (SSE) and POST (JSON-RPC).

    This follows the MCP Streamable HTTP specification (2025-03-26).
    - POST: Handle JSON-RPC messages (client-to-server)
    - GET: Establish SSE stream (server-to-client)
    - OPTIONS: CORS preflight
    - HEAD: Connection check
    """
    # Log incoming request for debugging
    print(f"[MCP] {request.method} {request.url}")
    print(f"[MCP] Headers: {dict(request.headers)}")

    # Handle OPTIONS for CORS preflight
    if request.method == "OPTIONS":
        print("[MCP] Handling OPTIONS preflight")
        return JSONResponse(
            content={"status": "ok"},
            headers={
                "Allow": "GET, POST, OPTIONS, HEAD",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS, HEAD",
                "Access-Control-Allow-Headers": "*",
            }
        )

    # Handle HEAD for connection checks
    if request.method == "HEAD":
        print("[MCP] Handling HEAD request")
        return JSONResponse(
            content={"status": "ok"},
            headers={"Allow": "GET, POST, OPTIONS, HEAD"}
        )

    if request.method == "POST":
        # Handle JSON-RPC message
        try:
            message = await request.json()
            print(f"[MCP] Received: {json.dumps(message, indent=2)}")

            method = message.get("method")
            msg_id = message.get("id")
            params = message.get("params", {})

            # Handle initialize request
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                            "resources": {}
                        },
                        "serverInfo": {
                            "name": "rpg-mcp-api",
                            "version": "0.1.0"
                        }
                    }
                }
                print(f"[MCP] Response: {json.dumps(response, indent=2)}")
                return JSONResponse(response)

            # Handle tools/list request
            elif method == "tools/list":
                tools = await bridge.list_tools()
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": tools}
                }
                print(f"[MCP] Returning {len(tools)} tools")
                return JSONResponse(response)

            # Handle tools/call request
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                print(f"[MCP] Calling tool: {tool_name}")
                result = await bridge.call_tool(tool_name, arguments)
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": result}
                }
                return JSONResponse(response)

            # Handle resources/list request
            elif method == "resources/list":
                resources = await bridge.list_resources()
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"resources": resources}
                }
                print(f"[MCP] Returning {len(resources)} resources")
                return JSONResponse(response)

            # Handle resources/read request
            elif method == "resources/read":
                uri = params.get("uri")
                print(f"[MCP] Reading resource: {uri}")
                resource = await bridge.read_resource(uri)
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"contents": [resource]}
                }
                return JSONResponse(response)

            # Unknown method
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
                print(f"[MCP] Unknown method: {method}")
                return JSONResponse(response, status_code=400)

        except Exception as e:
            print(f"[MCP] Error: {str(e)}")
            import traceback
            traceback.print_exc()
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id") if 'message' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            return JSONResponse(response, status_code=500)

    elif request.method == "GET":
        # Handle SSE stream
        print("[MCP] Establishing SSE stream")

        async def event_stream():
            """Generate SSE events for server-to-client messages."""
            try:
                # Send endpoint event per MCP spec
                yield f"event: endpoint\n"
                yield f"data: /mcp\n\n"
                print("[MCP] SSE stream established")

                # Keep connection alive for server-initiated messages
                while True:
                    if await request.is_disconnected():
                        print("[MCP] Client disconnected")
                        break

                    # Heartbeat every 30 seconds
                    await asyncio.sleep(30)
                    yield f": heartbeat\n\n"

            except Exception as e:
                print(f"[MCP] SSE error: {str(e)}")
                error_msg = json.dumps({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"SSE stream error: {str(e)}"
                    }
                })
                yield f"event: message\n"
                yield f"data: {error_msg}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )


@app.get("/tools")
async def list_tools():
    """
    List available MCP tools.

    This is a convenience endpoint for discovering available tools.
    """
    try:
        tools = await bridge.list_tools()
        return {"tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    """
    Call a specific MCP tool.

    Args:
        tool_name: Name of the tool to call
        request: Request containing tool arguments in body

    Returns:
        Tool execution result
    """
    try:
        arguments = await request.json()
        result = await bridge.call_tool(tool_name, arguments)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/resources")
async def list_resources():
    """List available MCP resources."""
    try:
        resources = await bridge.list_resources()
        return {"resources": resources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/resources/{uri:path}")
async def read_resource(uri: str):
    """Read a specific resource by URI."""
    try:
        resource = await bridge.read_resource(uri)
        return resource
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True
    )
