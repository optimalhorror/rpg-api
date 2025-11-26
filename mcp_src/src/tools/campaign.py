import json
import shutil
from uuid import uuid4

from mcp.types import Tool, TextContent

from utils import CAMPAIGNS_DIR, slugify, load_campaign_list, save_campaign_list, err_required, err_not_found
from repos import campaign_repo, npc_repo


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
                    "description": "The name of the campaign"
                },
                "player_name": {
                    "type": "string",
                    "description": "The player character's name"
                },
                "player_description": {
                    "type": "string",
                    "description": "Optional: Player character description (appearance, personality, backstory, etc.)"
                }
            },
            "required": ["name", "player_name"]
        }
    )


async def handle_begin_campaign(arguments: dict) -> list[TextContent]:
    """Handle the begin_campaign tool call."""
    try:
        campaign_name = arguments.get("name")
        player_name = arguments.get("player_name")
        player_description = arguments.get("player_description", "The player character")
        player_health = 25  # All players start with 25 HP

        if not campaign_name:
            return [TextContent(text=err_required("name"))]

        if not player_name:
            return [TextContent(text=err_required("player_name"))]

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
        campaign_repo.save_campaign(campaign_id, campaign_data)

        # Create player NPC file
        player_data = {
            "name": player_name,
            "keywords": [player_name.lower(), "player", "you", "user"],
            "arc": player_description,
            "health": player_health,
            "max_health": player_health,
            "hit_chance": 50,  # Default hit chance
            "inventory": {
                "money": 0,
                "items": {}
            }
        }

        # Save player NPC via repository (now campaign_id exists in list)
        npc_repo.save_npc(campaign_id, player_slug, player_data)

        # Create npcs.json index with player
        # Keywords like "user", "player", "you" are already in the player NPC's keywords array
        npcs_index = {
            player_slug: {
                "keywords": player_data["keywords"],
                "file": f"npc-{player_slug}.json"
            }
        }

        # Save NPC index via repository
        npc_repo.save_npc_index(campaign_id, npcs_index)

        return [TextContent(
            type="text",
            text=f"Campaign '{campaign_name}' created successfully!\n\nCampaign ID: {campaign_id}\nPlayer: {player_name} ({player_health} HP)\nDirectory: campaigns/{campaign_slug}/\n\nNote: Use add_item to give {player_name} weapons."
        )]

    except Exception as e:
        return [TextContent(text=f"Error creating campaign: {str(e)}")]


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
            return [TextContent(text=err_not_found("Campaign", campaign_id))]

        # Get campaign name before deleting
        campaign_data = campaign_repo.get_campaign(campaign_id)
        campaign_name = campaign_data.get("name", "Unknown") if campaign_data else "Unknown"

        # Delete campaign directory and all contents
        campaign_dir = CAMPAIGNS_DIR / campaign_slug
        if campaign_dir.exists():
            shutil.rmtree(campaign_dir)

        # Remove from campaign list
        del campaign_list[campaign_id]
        save_campaign_list(campaign_list)

        return [TextContent(
            type="text",
            text=f"Campaign '{campaign_name}' (ID: {campaign_id}) has been permanently deleted.\n\nRemoved:\n- Directory: campaigns/{campaign_slug}/\n- All NPCs, bestiary entries, and combat data\n- Campaign list entry"
        )]

    except Exception as e:
        return [TextContent(text=f"Error deleting campaign: {str(e)}")]
