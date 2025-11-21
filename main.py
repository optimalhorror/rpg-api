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

# CORS middleware
if Config.ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=Config.ALLOWED_ORIGINS,
        allow_credentials=True,
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


@app.post("/messages")
async def handle_message(request: Request):
    """
    Handle MCP messages via HTTP POST.

    This endpoint receives JSON-RPC messages from clients.
    """
    message = await request.json()

    # TODO: Process message through MCP server
    # For now, return echo
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {"echo": message}
    }


@app.get("/sse")
async def sse_endpoint(request: Request):
    """
    Server-Sent Events endpoint for receiving messages from the server.

    This endpoint streams messages from the MCP server to the client.
    """
    async def event_stream():
        """Generate SSE events."""
        try:
            # Send initial connection event
            yield f"event: connected\n"
            yield f"data: {{'status': 'connected'}}\n\n"

            # TODO: Connect to MCP server and stream events
            # For now, keep connection alive
            while True:
                if await request.is_disconnected():
                    break

                # Heartbeat every 30 seconds
                import asyncio
                await asyncio.sleep(30)
                yield f"event: heartbeat\n"
                yield f"data: {{'status': 'alive'}}\n\n"

        except Exception as e:
            yield f"event: error\n"
            yield f"data: {{'error': '{str(e)}'}}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
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
