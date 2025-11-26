from mcp.types import Tool, TextContent

from utils import err_already_exists
from repos import bestiary_repo


def get_create_bestiary_entry_tool() -> Tool:
    """Return the create_bestiary_entry tool definition."""
    return Tool(
        name="create_bestiary_entry",
        description="Create a bestiary entry (enemy template) with stats and weapons. These templates are used as baselines when creating combat participants. Use list_campaigns to get campaign_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (use list_campaigns to get this)"
                },
                "name": {
                    "type": "string",
                    "description": "Creature type name"
                },
                "threat_level": {
                    "type": "string",
                    "enum": ["none", "negligible", "low", "moderate", "high", "deadly", "certain_death"],
                    "description": "How dangerous this creature is: none (fly, 10% hit), negligible (dog, 25%), low (wolf, 35%), moderate (bandit, 50%), high (mercenary, 65%), deadly (dragon, 80%), certain_death (eldritch horror, 95%)"
                },
                "hp": {
                    "type": "string",
                    "description": "HP formula using standard dice notation (XdY+Z)"
                },
                "weapons": {
                    "type": "object",
                    "description": "REQUIRED: Map of attack names to damage formulas. Format: {\"attack_name\": \"XdY\"}",
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
        bestiary = bestiary_repo.get_bestiary(campaign_id)

        # Check if entry already exists
        entry_key = name.lower()
        if entry_key in bestiary:
            existing_entry = bestiary[entry_key]
            weapon_list = ", ".join([f"{w} ({d})" for w, d in existing_entry.get("weapons", {}).items()])
            details = f"Existing: {existing_entry.get('threat_level')}, {existing_entry.get('hp')} HP, {weapon_list}. Use get_bestiary to view."
            return [TextContent(text=err_already_exists("Bestiary entry", name, details))]

        # Add entry
        bestiary[entry_key] = {
            "threat_level": threat_level,
            "hp": hp,
            "weapons": weapons
        }

        # Save via repository
        bestiary_repo.save_bestiary(campaign_id, bestiary)

        weapon_list = ", ".join([f"{w} ({d})" for w, d in weapons.items()])
        return [TextContent(
            type="text",
            text=f"Bestiary entry '{name}' created successfully!\n\nThreat Level: {threat_level}\nHP: {hp}\nWeapons: {weapon_list}"
        )]

    except Exception as e:
        return [TextContent(text=f"Error creating bestiary entry: {str(e)}")]
