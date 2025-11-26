import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Prompt, GetPromptResult, ResourceTemplate

from tools import (
    get_begin_campaign_tool,
    handle_begin_campaign,
    get_delete_campaign_tool,
    handle_delete_campaign,
    get_create_npc_tool,
    handle_create_npc,
    get_heal_npc_tool,
    handle_heal_npc,
    get_attack_tool,
    handle_attack,
    get_remove_from_combat_tool,
    handle_remove_from_combat,
    get_spawn_enemy_tool,
    handle_spawn_enemy,
    get_create_bestiary_entry_tool,
    handle_create_bestiary_entry,
    # Inventory tools
    get_add_item_tool,
    handle_add_item,
    get_remove_item_tool,
    handle_remove_item,
    get_update_item_tool,
    handle_update_item,
    get_get_inventory_tool,
    handle_get_inventory,
    get_add_money_tool,
    handle_add_money,
    get_remove_money_tool,
    handle_remove_money,
    # Resource readers
    get_list_campaigns_tool,
    handle_list_campaigns,
    get_get_campaign_tool,
    handle_get_campaign,
    get_list_npcs_tool,
    handle_list_npcs,
    get_get_npc_tool,
    handle_get_npc,
    get_get_combat_status_tool,
    handle_get_combat_status,
    get_get_bestiary_tool,
    handle_get_bestiary,
)
from resources import list_resources, read_resource


app = Server("rpg-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        get_begin_campaign_tool(),
        get_delete_campaign_tool(),
        get_create_npc_tool(),
        get_heal_npc_tool(),
        get_create_bestiary_entry_tool(),
        get_attack_tool(),
        get_remove_from_combat_tool(),
        get_spawn_enemy_tool(),
        # Inventory tools
        get_add_item_tool(),
        get_remove_item_tool(),
        get_update_item_tool(),
        get_get_inventory_tool(),
        get_add_money_tool(),
        get_remove_money_tool(),
        # Resource readers
        get_list_campaigns_tool(),
        get_get_campaign_tool(),
        get_list_npcs_tool(),
        get_get_npc_tool(),
        get_get_combat_status_tool(),
        get_get_bestiary_tool(),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "begin_campaign":
        return await handle_begin_campaign(arguments)

    elif name == "delete_campaign":
        return await handle_delete_campaign(arguments)

    elif name == "create_npc":
        return await handle_create_npc(arguments)

    elif name == "heal_npc":
        return await handle_heal_npc(arguments)

    elif name == "create_bestiary_entry":
        return await handle_create_bestiary_entry(arguments)

    elif name == "attack":
        return await handle_attack(arguments)

    elif name == "remove_from_combat":
        return await handle_remove_from_combat(arguments)

    elif name == "spawn_enemy":
        return await handle_spawn_enemy(arguments)

    # Inventory tools
    elif name == "add_item":
        return await handle_add_item(arguments)

    elif name == "remove_item":
        return await handle_remove_item(arguments)

    elif name == "update_item":
        return await handle_update_item(arguments)

    elif name == "get_inventory":
        return await handle_get_inventory(arguments)

    elif name == "add_money":
        return await handle_add_money(arguments)

    elif name == "remove_money":
        return await handle_remove_money(arguments)

    # Resource readers
    elif name == "list_campaigns":
        return await handle_list_campaigns(arguments)

    elif name == "get_campaign":
        return await handle_get_campaign(arguments)

    elif name == "list_npcs":
        return await handle_list_npcs(arguments)

    elif name == "get_npc":
        return await handle_get_npc(arguments)

    elif name == "get_combat_status":
        return await handle_get_combat_status(arguments)

    elif name == "get_bestiary":
        return await handle_get_bestiary(arguments)

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
