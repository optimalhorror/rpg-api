"""Resource reader tools - expose MCP resources as callable tools."""
from mcp.types import Tool, TextContent

from utils import health_description
from repos import campaign_repo, npc_repo, bestiary_repo, combat_repo


def get_list_campaigns_tool() -> Tool:
    """Return the list_campaigns tool definition."""
    return Tool(
        name="list_campaigns",
        description="List all available RPG campaigns. Returns campaign IDs, names, and slugs.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    )


async def handle_list_campaigns(arguments: dict) -> list[TextContent]:
    """Handle the list_campaigns tool call."""
    # Use repository to get campaign list
    campaign_list = campaign_repo.list_campaigns()

    if not campaign_list:
        return [TextContent(
            type="text",
            text="No campaigns found. Create one with begin_campaign!"
        )]

    campaigns = []
    for campaign_id, campaign_slug in campaign_list.items():
        campaign_data = campaign_repo.get_campaign(campaign_id)
        if campaign_data:
            campaigns.append({
                "id": campaign_id,
                "name": campaign_data.get("name", "Unknown"),
                "slug": campaign_slug
            })

    result = "Available campaigns:\n\n"
    for campaign in campaigns:
        result += f"- {campaign['name']}\n"
        result += f"  ID: {campaign['id']}\n"
        result += f"  Slug: {campaign['slug']}\n\n"

    return [TextContent(type="text", text=result)]


def get_get_campaign_tool() -> Tool:
    """Return the get_campaign tool definition."""
    return Tool(
        name="get_campaign",
        description="Get full campaign details by campaign ID. Returns campaign data including player info.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (get from list_campaigns)"
                }
            },
            "required": ["campaign_id"]
        }
    )


async def handle_get_campaign(arguments: dict) -> list[TextContent]:
    """Handle the get_campaign tool call."""
    campaign_id = arguments.get("campaign_id")

    if not campaign_id:
        return [TextContent(type="text", text="Error: campaign_id is required")]

    campaign_data = campaign_repo.get_campaign(campaign_id)
    if not campaign_data:
        return [TextContent(type="text", text=f"Error: Campaign not found: {campaign_id}")]

    player_info = campaign_data.get('player', {})
    result = f"Campaign: {campaign_data.get('name')}\n"
    result += f"ID: {campaign_data.get('id')}\n"
    result += f"Player: {player_info.get('name', 'Unknown')}\n"
    result += f"Player File: {player_info.get('file', 'N/A')}\n"

    return [TextContent(type="text", text=result)]


def get_list_npcs_tool() -> Tool:
    """Return the list_npcs tool definition."""
    return Tool(
        name="list_npcs",
        description="List all NPCs in a campaign with their keywords. Use this to find NPC names before calling get_npc.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID"
                }
            },
            "required": ["campaign_id"]
        }
    )


async def handle_list_npcs(arguments: dict) -> list[TextContent]:
    """Handle the list_npcs tool call."""
    campaign_id = arguments.get("campaign_id")

    if not campaign_id:
        return [TextContent(type="text", text="Error: campaign_id is required")]

    npcs_data = npc_repo.get_npc_index(campaign_id)
    if not npcs_data:
        return [TextContent(type="text", text="No NPCs found in this campaign.")]

    result = "NPCs in campaign:\n\n"
    for npc_key, npc_info in npcs_data.items():
        keywords = ", ".join(npc_info.get("keywords", []))
        result += f"- {npc_key}\n"
        result += f"  Keywords: {keywords}\n"
        result += f"  File: {npc_info.get('file')}\n\n"

    return [TextContent(type="text", text=result)]


def get_get_npc_tool() -> Tool:
    """Return the get_npc tool definition."""
    return Tool(
        name="get_npc",
        description="Get full NPC details including stats, health, weapons, and description. Use list_npcs first to find the NPC key.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID"
                },
                "npc_key": {
                    "type": "string",
                    "description": "The NPC key from list_npcs (e.g., 'aragorn', 'user')"
                }
            },
            "required": ["campaign_id", "npc_key"]
        }
    )


async def handle_get_npc(arguments: dict) -> list[TextContent]:
    """Handle the get_npc tool call."""
    campaign_id = arguments.get("campaign_id")
    npc_key = arguments.get("npc_key")

    if not campaign_id:
        return [TextContent(type="text", text="Error: campaign_id is required")]

    if not npc_key:
        return [TextContent(type="text", text="Error: npc_key is required")]

    npc_data = npc_repo.get_npc(campaign_id, npc_key.lower())
    if not npc_data:
        return [TextContent(type="text", text=f"Error: NPC not found: {npc_key}")]

    # Narrative presentation (hide mechanics)
    health = npc_data.get('health', 20)
    max_health = npc_data.get('max_health', 20)
    health_status = health_description(health, max_health)

    result = f"NPC: {npc_data.get('name')}\n"
    result += f"Condition: {health_status}\n"

    # Get inventory weapons
    inventory_weapons = []
    if "inventory" in npc_data and "items" in npc_data["inventory"]:
        items = npc_data["inventory"]["items"]
        inventory_weapons = [
            (name, item.get("damage", "?"))
            for name, item in items.items()
            if item.get("weapon")
        ]

    if inventory_weapons:
        weapon_list = ", ".join([f"{w} ({d})" for w, d in inventory_weapons])
        result += f"Weapons: {weapon_list}\n"

    arc = npc_data.get("arc", "")
    if arc:
        result += f"Description: {arc}\n"

    keywords = npc_data.get("keywords", [])
    if keywords:
        result += f"Keywords: {', '.join(keywords)}\n"

    # Show inventory
    inventory = npc_data.get("inventory", {})
    if inventory:
        result += f"\n--- Inventory ---\n"
        result += f"Money: {inventory.get('money', 0)} gold\n"
        items = inventory.get("items", {})
        if items:
            result += f"Items ({len(items)}):\n"
            for item_name, item in items.items():
                result += f"  • {item_name}"
                if item.get("weapon"):
                    result += f" [weapon, {item.get('damage', '?')} damage]"
                result += f"\n    {item.get('description', 'No description')}\n"
        else:
            result += "Items: None\n"

    return [TextContent(type="text", text=result)]


def get_get_combat_status_tool() -> Tool:
    """Return the get_combat_status tool definition."""
    return Tool(
        name="get_combat_status",
        description="Get current combat state showing all participants, their health, and turn order. Returns empty if no combat is active.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID"
                }
            },
            "required": ["campaign_id"]
        }
    )


async def handle_get_combat_status(arguments: dict) -> list[TextContent]:
    """Handle the get_combat_status tool call."""
    campaign_id = arguments.get("campaign_id")

    if not campaign_id:
        return [TextContent(type="text", text="Error: campaign_id is required")]

    combat_data = combat_repo.get_combat_state(campaign_id)
    if not combat_data:
        return [TextContent(type="text", text="No active combat.")]

    result = "=== COMBAT STATUS ===\n\n"

    participants = combat_data.get("participants", {})
    if participants:
        result += "Participants:\n"
        for name, stats in participants.items():
            health = stats.get("health", 20)
            max_health = stats.get("max_health", 20)
            team = stats.get("team", "?")
            health_status = health_description(health, max_health)
            result += f"- {name} (Team {team}): {health_status}\n"
    else:
        result += "No participants in combat.\n"

    return [TextContent(type="text", text=result)]


def get_get_bestiary_tool() -> Tool:
    """Return the get_bestiary tool definition."""
    return Tool(
        name="get_bestiary",
        description="Get all enemy templates with their stats and weapons. Use this to see available enemy types.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID"
                }
            },
            "required": ["campaign_id"]
        }
    )


async def handle_get_bestiary(arguments: dict) -> list[TextContent]:
    """Handle the get_bestiary tool call."""
    campaign_id = arguments.get("campaign_id")

    if not campaign_id:
        return [TextContent(type="text", text="Error: campaign_id is required")]

    bestiary_data = bestiary_repo.get_bestiary(campaign_id)
    if not bestiary_data:
        return [TextContent(type="text", text="No bestiary found. Create enemy templates with create_bestiary_entry.")]

    result = "=== BESTIARY ===\n\n"

    for enemy_type, enemy_data in bestiary_data.items():
        result += f"{enemy_type}:\n"
        result += f"  Threat Level: {enemy_data.get('threat_level', 'moderate')}\n"
        result += f"  Health: {enemy_data.get('hp')}\n"

        weapons = enemy_data.get("weapons", {})
        if weapons:
            weapon_list = ", ".join([f"{w} ({d})" for w, d in weapons.items()])
            result += f"  Weapons: {weapon_list}\n"

        description = enemy_data.get("description", "")
        if description:
            result += f"  Description: {description}\n"

        result += "\n"

    return [TextContent(type="text", text=result)]
