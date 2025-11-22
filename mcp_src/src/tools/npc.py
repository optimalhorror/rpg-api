from mcp.types import Tool, TextContent

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import slugify
from repository_json import JsonNPCRepository

# Global repository instance
_npc_repo = JsonNPCRepository()


def get_create_npc_tool() -> Tool:
    """Return the create_npc tool definition."""
    return Tool(
        name="create_npc",
        description="Create or update an NPC in the campaign. This adds them to the NPC index so they can be referenced later. To get the campaign_id, first read the campaign://list resource.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (get this by reading the campaign://list resource first)"
                },
                "name": {
                    "type": "string",
                    "description": "The NPC's name (e.g., 'Marcus', 'black-bearded-guard')"
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords to trigger this NPC's context (e.g., ['Marcus', 'guard', 'black beard'])"
                },
                "arc": {
                    "type": "string",
                    "description": "The NPC's story/description that will be injected into context"
                },
                "weapons": {
                    "type": "object",
                    "description": "Optional: Map of weapon names to damage formulas (e.g., {'sword': '1d6', 'dagger': '1d4'})",
                    "additionalProperties": {"type": "string"}
                },
                "health": {
                    "type": "integer",
                    "description": "Optional: Current health points. Defaults to max_health if not specified."
                },
                "max_health": {
                    "type": "integer",
                    "description": "Optional: Maximum health points. Defaults to 20 if not specified."
                },
                "hit_chance": {
                    "type": "integer",
                    "description": "Optional: Hit chance percentage (1-100). Defaults to 50 if not specified."
                }
            },
            "required": ["campaign_id", "name", "keywords", "arc"]
        }
    )


async def handle_create_npc(arguments: dict) -> list[TextContent]:
    """Handle the create_npc tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        npc_name = arguments["name"]
        keywords = arguments["keywords"]
        arc = arguments["arc"]
        weapons = arguments.get("weapons", {})
        max_health = arguments.get("max_health", 20)
        health = arguments.get("health", max_health)  # Default to max_health
        hit_chance = arguments.get("hit_chance", 50)  # Default to 50%

        npc_slug = slugify(npc_name)

        # Create NPC data
        npc_data = {
            "name": npc_name,
            "keywords": keywords,
            "arc": arc,
            "health": health,
            "max_health": max_health,
            "weapons": weapons,
            "hit_chance": hit_chance
        }

        # Save NPC via repository
        _npc_repo.save_npc(campaign_id, npc_slug, npc_data)

        # Update NPC index
        npcs_index = _npc_repo.get_npc_index(campaign_id)
        npcs_index[npc_slug] = {
            "keywords": keywords,
            "file": f"npc-{npc_slug}.json"
        }
        _npc_repo.save_npc_index(campaign_id, npcs_index)

        return [TextContent(
            type="text",
            text=f"NPC '{npc_name}' created successfully!\n\nFile: npc-{npc_slug}.json\nKeywords: {', '.join(keywords)}"
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Error creating NPC: {str(e)}")]
