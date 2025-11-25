from mcp.types import Tool, TextContent

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import slugify, roll_dice, health_description, healing_descriptor
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
                },
                "weapons": {
                    "type": "object",
                    "description": "Optional: Starting weapons added to inventory. Format: {\"Sword\": \"1d8\", \"Dagger\": \"1d4\"}",
                    "additionalProperties": {"type": "string"}
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
        max_health = arguments.get("max_health", 20)
        health = arguments.get("health", max_health)  # Default to max_health
        hit_chance = arguments.get("hit_chance", 50)  # Default to 50%
        weapons = arguments.get("weapons", {})

        npc_slug = slugify(npc_name)

        # Create NPC data
        npc_data = {
            "name": npc_name,
            "keywords": keywords,
            "arc": arc,
            "health": health,
            "max_health": max_health,
            "hit_chance": hit_chance,
            "inventory": {
                "money": 0,
                "items": {}
            }
        }

        # Add starting weapons to inventory
        for weapon_name, damage in weapons.items():
            npc_data["inventory"]["items"][weapon_name] = {
                "description": f"A {weapon_name.lower()}",
                "source": "starting equipment",
                "weapon": True,
                "damage": damage
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

        # Build success message
        message = f"NPC '{npc_name}' created successfully!\n\nFile: npc-{npc_slug}.json\nKeywords: {', '.join(keywords)}"

        if weapons:
            weapon_list = ", ".join([f"{name} ({damage})" for name, damage in weapons.items()])
            message += f"\nWeapons: {weapon_list}"

        return [TextContent(
            type="text",
            text=message
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Error creating NPC: {str(e)}")]


def get_heal_npc_tool() -> Tool:
    """Return the heal_npc tool definition."""
    return Tool(
        name="heal_npc",
        description="Heal an NPC by rolling healing dice (e.g., '1d4', '2d6'). Healing comes from items, rest, magic, etc. Cannot exceed max_health.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID"
                },
                "npc_name": {
                    "type": "string",
                    "description": "Name of the NPC to heal"
                },
                "heal_dice": {
                    "type": "string",
                    "description": "Healing dice formula (e.g., '1d4', '1d6', '2d8+2')"
                },
                "source": {
                    "type": "string",
                    "description": "Optional: Source of healing (e.g., 'potion', 'long rest', 'cure wounds spell')"
                }
            },
            "required": ["campaign_id", "npc_name", "heal_dice"]
        }
    )


async def handle_heal_npc(arguments: dict) -> list[TextContent]:
    """Handle the heal_npc tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        npc_name = arguments["npc_name"]
        heal_dice = arguments["heal_dice"]
        source = arguments.get("source", "healing")

        npc_slug = slugify(npc_name)

        npc_data = _npc_repo.get_npc(campaign_id, npc_slug)
        if not npc_data:
            return [TextContent(
                type="text",
                text=f"NPC '{npc_name}' not found in campaign"
            )]

        # Roll healing
        heal_amount = roll_dice(heal_dice)

        old_health = npc_data.get("health", 20)
        max_health = npc_data.get("max_health", 20)

        # Apply healing, cap at max_health
        new_health = min(old_health + heal_amount, max_health)
        npc_data["health"] = new_health

        _npc_repo.save_npc(campaign_id, npc_slug, npc_data)

        # Narrative output (hide mechanics)
        source_str = f" from {source}" if source else ""

        # Special case: already at full health
        if old_health == max_health:
            return [TextContent(
                type="text",
                text=f"{npc_name} receives healing{source_str}, but is already in perfect health."
            )]

        # Get healing quality and health states
        healing_quality = healing_descriptor(heal_amount, heal_dice)
        old_state = health_description(old_health, max_health)
        new_state = health_description(new_health, max_health)

        # Build narrative message
        result_lines = [f"{npc_name} receives {healing_quality}{source_str}."]

        # Special case: fully restored to perfect health
        if new_health == max_health:
            result_lines.append(f"{npc_name} is fully restored to perfect health.")
        else:
            # Show health state transition
            result_lines.append(f"{npc_name} recovers from {old_state} to {new_state}.")

        return [TextContent(
            type="text",
            text="\n".join(result_lines)
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Error healing NPC: {str(e)}")]
