import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Prompt, GetPromptResult, ResourceTemplate

from tools import get_all_tools, call_tool as tools_call_tool
from resources import list_resources, read_resource


app = Server("rpg-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return get_all_tools()


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    return await tools_call_tool(name, arguments)


@app.list_resources()
async def handle_list_resources():
    """List available resources."""
    return await list_resources()


@app.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read resource content by URI."""
    return await read_resource(uri)


@app.list_prompts()
async def handle_list_prompts() -> list[Prompt]:
    """List available prompts."""
    return []


@app.get_prompt()
async def handle_get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    """Get a prompt by name."""
    raise ValueError(f"Prompt not found: {name}")


@app.list_resource_templates()
async def handle_list_resource_templates() -> list[ResourceTemplate]:
    """List available resource templates."""
    return []


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
