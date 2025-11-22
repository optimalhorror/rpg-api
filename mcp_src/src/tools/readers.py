"""Resource reader tools - expose MCP resources as callable tools."""
import json
import sys
from pathlib import Path

from mcp.types import Tool, TextContent

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import CAMPAIGNS_DIR
from repository_json import (
    JsonCampaignRepository,
    JsonNPCRepository,
    JsonBestiaryRepository,
    JsonCombatRepository,
)

# Global repository instances
_campaign_repo = JsonCampaignRepository()
_npc_repo = JsonNPCRepository()
_bestiary_repo = JsonBestiaryRepository()
_combat_repo = JsonCombatRepository()


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
    campaigns = []

    if CAMPAIGNS_DIR.exists():
        for campaign_dir in CAMPAIGNS_DIR.iterdir():
            if campaign_dir.is_dir():
                campaign_file = campaign_dir / "campaign.json"
                if campaign_file.exists():
                    campaign_data = json.loads(campaign_file.read_text())
                    campaigns.append({
                        "id": campaign_data.get("id"),
                        "name": campaign_data.get("name"),
                        "slug": campaign_dir.name
                    })

    if not campaigns:
        return [TextContent(
            type="text",
            text="No campaigns found. Create one with begin_campaign!"
        )]

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

    campaign_data = _campaign_repo.get_campaign(campaign_id)
    if not campaign_data:
        return [TextContent(type="text", text=f"Error: Campaign not found: {campaign_id}")]

    result = f"Campaign: {campaign_data.get('name')}\n"
    result += f"ID: {campaign_data.get('id')}\n"
    result += f"Player: {campaign_data.get('player', {}).get('name', 'Unknown')}\n"
    result += f"\nFull data:\n{json.dumps(campaign_data, indent=2)}"

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

    npcs_data = _npc_repo.get_npc_index(campaign_id)
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

    npc_data = _npc_repo.get_npc(campaign_id, npc_key.lower())
    if not npc_data:
        return [TextContent(type="text", text=f"Error: NPC not found: {npc_key}")]

    result = f"NPC: {npc_data.get('name')}\n"
    result += f"Health: {npc_data.get('health')}/{npc_data.get('max_health')}\n"
    result += f"Hit Chance: {npc_data.get('hit_chance', 50)}%\n"

    weapons = npc_data.get("weapons", {})
    if weapons:
        weapon_list = ", ".join([f"{w} ({d})" for w, d in weapons.items()])
        result += f"Weapons: {weapon_list}\n"

    arc = npc_data.get("arc", "")
    if arc:
        result += f"Description: {arc}\n"

    keywords = npc_data.get("keywords", [])
    if keywords:
        result += f"Keywords: {', '.join(keywords)}\n"

    result += f"\nFull data:\n{json.dumps(npc_data, indent=2)}"

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

    combat_data = _combat_repo.get_combat_state(campaign_id)
    if not combat_data:
        return [TextContent(type="text", text="No active combat.")]

    result = "=== COMBAT STATUS ===\n\n"

    participants = combat_data.get("participants", {})
    if participants:
        result += "Participants:\n"
        for name, stats in participants.items():
            health = stats.get("health")
            max_health = stats.get("max_health")
            team = stats.get("team", "?")
            hit_chance = stats.get("hit_chance", 50)
            result += f"- {name} (Team {team}): {health}/{max_health} HP, {hit_chance}% hit chance\n"
    else:
        result += "No participants in combat.\n"

    result += f"\nFull combat data:\n{json.dumps(combat_data, indent=2)}"

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

    bestiary_data = _bestiary_repo.get_bestiary(campaign_id)
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

    result += f"Full bestiary data:\n{json.dumps(bestiary_data, indent=2)}"

    return [TextContent(type="text", text=result)]
