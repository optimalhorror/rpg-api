from mcp.types import Tool, TextContent

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from repository_json import JsonBestiaryRepository

# Global repository instance (can be swapped for different implementations)
_bestiary_repo = JsonBestiaryRepository()


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
                "threat_level": {
                    "type": "string",
                    "enum": ["none", "negligible", "low", "moderate", "high", "deadly", "certain_death"],
                    "description": "How dangerous this creature is: none (fly, 10% hit), negligible (dog, 25%), low (wolf, 35%), moderate (bandit, 50%), high (mercenary, 65%), deadly (dragon, 80%), certain_death (eldritch horror, 95%)"
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
            "required": ["campaign_id", "name", "threat_level", "hp", "weapons"]
        }
    )


async def handle_create_bestiary_entry(arguments: dict) -> list[TextContent]:
    """Handle the create_bestiary_entry tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        name = arguments["name"]
        threat_level = arguments["threat_level"]
        hp = arguments["hp"]
        weapons = arguments["weapons"]

        # Load bestiary via repository
        bestiary = _bestiary_repo.get_bestiary(campaign_id)

        # Add/update entry
        bestiary[name.lower()] = {
            "threat_level": threat_level,
            "hp": hp,
            "weapons": weapons
        }

        # Save via repository
        _bestiary_repo.save_bestiary(campaign_id, bestiary)

        weapon_list = ", ".join([f"{w} ({d})" for w, d in weapons.items()])
        return [TextContent(
            type="text",
            text=f"Bestiary entry '{name}' created successfully!\n\nThreat Level: {threat_level}\nHP: {hp}\nWeapons: {weapon_list}"
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Error creating bestiary entry: {str(e)}")]
