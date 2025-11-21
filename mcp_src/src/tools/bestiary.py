import json

from mcp.types import Tool, TextContent

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import get_campaign_dir


def get_create_bestiary_entry_tool() -> Tool:
    """Return the create_bestiary_entry tool definition."""
    return Tool(
        name="create_bestiary_entry",
        description="Create or update a bestiary entry (enemy template) with stats and weapons. These templates are used as baselines when creating combat participants. To get the campaign_id, first read the campaign://list resource.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (get this by reading the campaign://list resource first)"
                },
                "name": {
                    "type": "string",
                    "description": "Template name (e.g., 'guard', 'goblin', 'dragon')"
                },
                "hp": {
                    "type": "string",
                    "description": "HP formula in dice notation (e.g., '15+1d6', '20', '10+2d4')"
                },
                "weapons": {
                    "type": "object",
                    "description": "Map of weapon names to damage formulas (e.g., {'sword': '1d6', 'dagger': '1d4'})",
                    "additionalProperties": {"type": "string"}
                }
            },
            "required": ["campaign_id", "name", "hp", "weapons"]
        }
    )


async def handle_create_bestiary_entry(arguments: dict) -> list[TextContent]:
    """Handle the create_bestiary_entry tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        name = arguments["name"]
        hp = arguments["hp"]
        weapons = arguments["weapons"]

        campaign_dir = get_campaign_dir(campaign_id)
        bestiary_file = campaign_dir / "bestiary.json"

        # Load or create bestiary
        if bestiary_file.exists():
            bestiary = json.loads(bestiary_file.read_text())
        else:
            bestiary = {}

        # Add/update entry
        bestiary[name.lower()] = {
            "hp": hp,
            "weapons": weapons
        }

        bestiary_file.write_text(json.dumps(bestiary, indent=2))

        weapon_list = ", ".join([f"{w} ({d})" for w, d in weapons.items()])
        return [TextContent(
            type="text",
            text=f"Bestiary entry '{name}' created successfully!\n\nHP: {hp}\nWeapons: {weapon_list}"
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Error creating bestiary entry: {str(e)}")]
