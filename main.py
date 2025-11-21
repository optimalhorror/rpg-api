"""FastAPI SSE transport for RPG MCP Server."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import Config


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
    # Import MCP server to get tools
    try:
        from server import app as mcp_app

        # Get tools from MCP server
        tools = await mcp_app._list_tools_handler()

        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                }
                for tool in tools
            ]
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True
    )
