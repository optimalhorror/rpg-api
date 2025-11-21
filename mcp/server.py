import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Prompt, GetPromptResult, ResourceTemplate

from tools import (
    get_begin_campaign_tool,
    handle_begin_campaign,
    get_create_npc_tool,
    handle_create_npc,
    get_attack_tool,
    handle_attack,
    get_remove_from_combat_tool,
    handle_remove_from_combat,
    get_create_bestiary_entry_tool,
    handle_create_bestiary_entry,
)
from resources import list_resources, read_resource


app = Server("rpg-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        get_begin_campaign_tool(),
        get_create_npc_tool(),
        get_create_bestiary_entry_tool(),
        get_attack_tool(),
        get_remove_from_combat_tool(),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "begin_campaign":
        return await handle_begin_campaign(arguments)

    elif name == "create_npc":
        return await handle_create_npc(arguments)

    elif name == "create_bestiary_entry":
        return await handle_create_bestiary_entry(arguments)

    elif name == "attack":
        return await handle_attack(arguments)

    elif name == "remove_from_combat":
        return await handle_remove_from_combat(arguments)

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


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
