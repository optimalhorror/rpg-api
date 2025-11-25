from uuid import uuid4

from mcp.types import Tool, TextContent

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import CAMPAIGNS_DIR, slugify, load_campaign_list, save_campaign_list
from repository_json import JsonCampaignRepository, JsonPlayerRepository, JsonNPCRepository

# Global repository instances
_campaign_repo = JsonCampaignRepository()
_player_repo = JsonPlayerRepository()
_npc_repo = JsonNPCRepository()


def get_begin_campaign_tool() -> Tool:
    """Return the begin_campaign tool definition."""
    return Tool(
        name="begin_campaign",
        description="Create a new RPG campaign with a name and player character. Returns the campaign ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the campaign (e.g., 'The Lost Kingdom')"
                },
                "player_name": {
                    "type": "string",
                    "description": "The player character's name (e.g., 'Aragorn', 'user')"
                },
                "player_description": {
                    "type": "string",
                    "description": "Optional: Player character description (appearance, personality, backstory, etc.)"
                },
                "player_health": {
                    "type": "integer",
                    "description": "Optional: Player's max health. Defaults to 20."
                },
                "player_weapons": {
                    "type": "object",
                    "description": "Optional: Player's starting weapons (e.g., {'sword': '1d6', 'fists': '1d4'}). Omit this field to default to fists.",
                    "additionalProperties": {"type": "string"},
                    "default": {}
                }
            },
            "required": ["name", "player_name"]
        }
    )


async def handle_begin_campaign(arguments: dict) -> list[TextContent]:
    """Handle the begin_campaign tool call."""
    campaign_name = arguments.get("name")
    player_name = arguments.get("player_name")
    player_description = arguments.get("player_description", "The player character")
    player_health = arguments.get("player_health", 20)
    player_weapons = arguments.get("player_weapons")

    # Default to fists only if no weapons provided (None or empty dict)
    if not player_weapons:
        player_weapons = {"fists": "1d4"}

    if not campaign_name:
        return [TextContent(type="text", text="Error: Campaign name is required")]

    if not player_name:
        return [TextContent(type="text", text="Error: Player name is required")]

    # Generate unique ID and slug
    campaign_id = str(uuid4())
    campaign_slug = slugify(campaign_name)

    # Create campaign directory
    campaign_dir = CAMPAIGNS_DIR / campaign_slug
    campaign_dir.mkdir(parents=True, exist_ok=True)

    # Create campaign.json with player reference
    player_slug = slugify(player_name)
    campaign_data = {
        "id": campaign_id,
        "name": campaign_name,
        "player": {
            "name": player_name,
            "file": f"npc-{player_slug}.json"
        }
    }

    # IMPORTANT: Add to campaign list FIRST so repository can find the campaign
    campaign_list = load_campaign_list()
    campaign_list[campaign_id] = campaign_slug
    save_campaign_list(campaign_list)

    # Save campaign data via repository
    campaign_file = campaign_dir / "campaign.json"
    import json
    campaign_file.write_text(json.dumps(campaign_data, indent=2))

    # Create player NPC file
    player_data = {
        "name": player_name,
        "keywords": [player_name.lower(), "player", "you", "user"],
        "arc": player_description,
        "health": player_health,
        "max_health": player_health,
        "weapons": player_weapons
    }

    # Save player NPC via repository (now campaign_id exists in list)
    _npc_repo.save_npc(campaign_id, player_slug, player_data)

    # Create npcs.json index with player
    # Add both the player name and "user" as keys pointing to the same file
    npcs_index = {
        player_slug: {
            "keywords": player_data["keywords"],
            "file": f"npc-{player_slug}.json"
        },
        "user": {
            "keywords": ["user", "player", "you"],
            "file": f"npc-{player_slug}.json"
        }
    }

    # Save NPC index via repository
    _npc_repo.save_npc_index(campaign_id, npcs_index)

    weapon_list = ", ".join([f"{w} ({d})" for w, d in player_weapons.items()])
    return [TextContent(
        type="text",
        text=f"Campaign '{campaign_name}' created successfully!\n\nCampaign ID: {campaign_id}\nPlayer: {player_name} ({player_health} HP)\nWeapons: {weapon_list}\nDirectory: campaigns/{campaign_slug}/"
    )]


def get_delete_campaign_tool() -> Tool:
    """Return the delete_campaign tool definition."""
    return Tool(
        name="delete_campaign",
        description="Delete a campaign completely. Removes all files from storage and campaign list. WARNING: This is permanent and cannot be undone!",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID to delete"
                }
            },
            "required": ["campaign_id"]
        }
    )


async def handle_delete_campaign(arguments: dict) -> list[TextContent]:
    """Handle the delete_campaign tool call."""
    try:
        campaign_id = arguments["campaign_id"]

        # Load campaign list
        campaign_list = load_campaign_list()
        campaign_slug = campaign_list.get(campaign_id)

        if not campaign_slug:
            return [TextContent(type="text", text=f"Error: Campaign not found: {campaign_id}")]

        # Get campaign name before deleting
        campaign_dir = CAMPAIGNS_DIR / campaign_slug
        campaign_file = campaign_dir / "campaign.json"

        campaign_name = "Unknown"
        if campaign_file.exists():
            import json
            campaign_data = json.loads(campaign_file.read_text())
            campaign_name = campaign_data.get("name", "Unknown")

        # Delete campaign directory and all contents
        if campaign_dir.exists():
            import shutil
            shutil.rmtree(campaign_dir)

        # Remove from campaign list
        del campaign_list[campaign_id]
        save_campaign_list(campaign_list)

        return [TextContent(
            type="text",
            text=f"Campaign '{campaign_name}' (ID: {campaign_id}) has been permanently deleted.\n\nRemoved:\n- Directory: campaigns/{campaign_slug}/\n- All NPCs, bestiary entries, and combat data\n- Campaign list entry"
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Error deleting campaign: {str(e)}")]
