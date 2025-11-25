import random

from mcp.types import Tool, TextContent

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import get_campaign_dir, health_description, slugify, roll_dice, damage_descriptor
from repository_json import JsonNPCRepository, JsonBestiaryRepository, JsonCombatRepository, JsonCampaignRepository

# Global repository instances
_npc_repo = JsonNPCRepository()
_bestiary_repo = JsonBestiaryRepository()
_combat_repo = JsonCombatRepository()
_campaign_repo = JsonCampaignRepository()


def threat_level_to_hit_chance(threat_level: str) -> int:
    """Convert threat level to hit chance percentage."""
    threat_map = {
        "none": 10,           # fly - needs lucky eye bite
        "negligible": 25,     # dog - can hurt but not trained
        "low": 35,            # wolf - natural hunter
        "moderate": 50,       # bandit - trained fighter
        "high": 65,           # mercenary - professional
        "deadly": 80,         # dragon - apex predator
        "certain_death": 95   # eldritch horror - reality-bending
    }
    return threat_map.get(threat_level, 50)  # Default to 50% if unknown


def get_participant_stats(campaign_id: str, name: str) -> dict:
    """Get participant stats: check NPC file first, then bestiary, then defaults."""
    participant_slug = slugify(name)

    # 1. Check if existing NPC (load persisted health + weapons + hit_chance)
    npc_data = _npc_repo.get_npc(campaign_id, participant_slug)
    if npc_data:
        return {
            "health": npc_data.get("health", 20),
            "max_health": npc_data.get("max_health", 20),
            "weapons": npc_data.get("weapons", {}),
            "hit_chance": npc_data.get("hit_chance", 50)
        }

    # 2. Check bestiary for template (roll new stats + map threat to hit_chance)
    entry = _bestiary_repo.get_entry(campaign_id, name)
    if entry:
        max_health = roll_dice(entry["hp"])
        threat_level = entry.get("threat_level", "moderate")
        hit_chance = threat_level_to_hit_chance(threat_level)
        return {
            "health": max_health,
            "max_health": max_health,
            "weapons": entry.get("weapons", {}),
            "hit_chance": hit_chance
        }

    # 3. Default stats
    return {
        "health": 20,
        "max_health": 20,
        "weapons": {},
        "hit_chance": 50
    }


def get_attack_tool() -> Tool:
    """Return the attack tool definition."""
    return Tool(
        name="attack",
        description="Perform an attack action. Returns human-readable combat results including hit/miss, damage description, and health states. To get the campaign_id, first read the campaign://list resource.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (get this by reading the campaign://list resource first)"
                },
                "attacker": {
                    "type": "string",
                    "description": "Who is attacking (e.g., 'player', 'Marcus')"
                },
                "target": {
                    "type": "string",
                    "description": "Who is being attacked"
                },
                "weapon": {
                    "type": "string",
                    "description": "Weapon being used (e.g., 'sword', 'fists', 'dagger')"
                },
                "allied_with": {
                    "type": "string",
                    "description": "Optional: Name of participant this attacker is allied with (e.g., 'Marcus', 'player'). Creates or joins that team. To fight solo, use your own name. Anyone can later join your team by using your name in allied_with."
                }
            },
            "required": ["campaign_id", "attacker", "target", "weapon"]
        }
    )


async def handle_attack(arguments: dict) -> list[TextContent]:
    """Handle the attack tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        attacker = arguments["attacker"]
        target = arguments["target"]
        weapon = arguments["weapon"]
        allied_with = arguments.get("allied_with")

        # Load or create combat state via repository
        combat_state = _combat_repo.get_combat_state(campaign_id)
        if not combat_state:
            combat_state = {"participants": {}}

        # Initialize participants with team assignment
        for participant in [attacker, target]:
            if participant not in combat_state["participants"]:
                stats = get_participant_stats(campaign_id, participant)

                # Assign team (string-based)
                if participant == attacker and allied_with:
                    # Allied with someone - join their team or create team with their name
                    if allied_with in combat_state["participants"]:
                        # Copy ally's team
                        stats["team"] = combat_state["participants"][allied_with]["team"]
                    else:
                        # Ally doesn't exist yet, create team named after them
                        stats["team"] = allied_with
                else:
                    # No ally specified - solo team named after participant
                    stats["team"] = participant

                combat_state["participants"][participant] = stats

        # Simple combat: roll d20 for hit, using attacker's hit_chance
        attacker_data = combat_state["participants"][attacker]
        hit_chance = attacker_data.get("hit_chance", 50)
        hit_roll = random.randint(1, 20)
        # Convert hit_chance percentage to d20 threshold (e.g., 50% = >= 11, 75% = >= 6)
        hit_threshold = 21 - int(hit_chance * 20 / 100)
        hit = hit_roll >= hit_threshold

        result_lines = []

        if hit:
            # Get weapon damage: check inventory first, then base weapons, then validate
            attacker_data = combat_state["participants"][attacker]
            attacker_slug = slugify(attacker)
            damage_formula = None

            # Check if attacker is an NPC or monster (must use defined weapons only)
            npc_data = _npc_repo.get_npc(campaign_id, attacker_slug)
            bestiary_entry = _bestiary_repo.get_entry(campaign_id, attacker)
            is_defined_character = npc_data is not None or bestiary_entry is not None

            # 1. Check inventory for weapon (NPCs only)
            if npc_data and "inventory" in npc_data:
                inventory = npc_data["inventory"]
                items = inventory.get("items", {})
                # Look for matching weapon in inventory
                if weapon in items:
                    item = items[weapon]
                    if item.get("weapon") and item.get("damage"):
                        damage_formula = item["damage"]

            # 2. Fallback to base weapons (from NPC or bestiary)
            if not damage_formula:
                weapons = attacker_data.get("weapons", {})
                if weapon in weapons:
                    damage_formula = weapons[weapon]

            # 3. Validate weapon exists for NPCs/monsters, or allow freeform for others
            if not damage_formula:
                if is_defined_character:
                    # NPCs and monsters must use their defined weapons
                    available_weapons = attacker_data.get("weapons", {}).keys()
                    if npc_data and "inventory" in npc_data:
                        inventory_weapons = [
                            name for name, item in npc_data["inventory"].get("items", {}).items()
                            if item.get("weapon")
                        ]
                        available_weapons = list(available_weapons) + inventory_weapons

                    weapons_list = ", ".join(available_weapons) if available_weapons else "none"
                    return [TextContent(
                        type="text",
                        text=f"Error: {attacker} doesn't have '{weapon}'. Available weapons: {weapons_list}"
                    )]
                else:
                    # Unknown participants default to 1d6 (e.g., 'player', random names)
                    damage = random.randint(1, 6)
                    damage_formula = "1d6"

            # Roll damage if we have a formula
            if damage_formula and 'damage' not in locals():
                damage = roll_dice(damage_formula)

            hit_locations = ["head", "chest", "arm", "leg"]
            hit_location = random.choice(hit_locations)

            # Apply damage
            combat_state["participants"][target]["health"] -= damage
            combat_state["participants"][target]["health"] = max(0, combat_state["participants"][target]["health"])

            target_health = combat_state["participants"][target]["health"]
            target_max = combat_state["participants"][target]["max_health"]

            # Sync health to NPC file if target is an NPC (real-time tracking)
            target_slug = slugify(target)
            target_npc_data = _npc_repo.get_npc(campaign_id, target_slug)
            if target_npc_data:
                target_npc_data["health"] = target_health
                _npc_repo.save_npc(campaign_id, target_slug, target_npc_data)

            # Narrative output (hide mechanics)
            damage_desc = damage_descriptor(damage, damage_formula)
            result_lines.append(f"{attacker} attacks {target} with {weapon}.")
            result_lines.append(f"The weapon {damage_desc} into the {hit_location}.")

            # Check if target died
            if target_health <= 0:
                result_lines.append(f"{target} has been slain!")

                # Check if dead target is the player character
                campaign_data = _campaign_repo.get_campaign(campaign_id)
                player_name = campaign_data.get("player", {}).get("name", "") if campaign_data else ""
                is_player = target.lower() == player_name.lower()

                # Delete NPC file for non-player deaths
                if not is_player and target_npc_data:
                    _npc_repo.delete_npc(campaign_id, target_slug)

                # Remove dead target from combat
                del combat_state["participants"][target]

                # Check if combat should end (only one team remains)
                remaining_teams = set(p.get("team") for p in combat_state["participants"].values())
                if len(remaining_teams) <= 1:
                    # Sync remaining participants' health to NPC files if they exist
                    npcs_index = _npc_repo.get_npc_index(campaign_id)

                    for participant_name, participant_data in combat_state["participants"].items():
                        participant_slug = slugify(participant_name)

                        # Check if this participant is an NPC
                        if participant_slug in npcs_index:
                            npc_data = _npc_repo.get_npc(campaign_id, participant_slug)
                            if npc_data:
                                npc_data["health"] = participant_data["health"]
                                npc_data["max_health"] = participant_data["max_health"]
                                _npc_repo.save_npc(campaign_id, participant_slug, npc_data)

                    _combat_repo.delete_combat_state(campaign_id)
                    result_lines.append("\nCombat has ended!")
            else:
                result_lines.append(f"{target} is {health_description(target_health, target_max)}.")
        else:
            result_lines.append(f"{attacker} attacks {target} with {weapon}.")
            result_lines.append(f"{target} dodges the attack.")

            # Show target health even on miss
            if target in combat_state["participants"]:
                target_health = combat_state["participants"][target]["health"]
                target_max = combat_state["participants"][target]["max_health"]
                result_lines.append(f"{target} is {health_description(target_health, target_max)}.")

        # Save combat state via repository
        _combat_repo.save_combat_state(campaign_id, combat_state)

        return [TextContent(type="text", text="\n".join(result_lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error in attack: {str(e)}")]


def get_remove_from_combat_tool() -> Tool:
    """Return the remove_from_combat tool definition."""
    return Tool(
        name="remove_from_combat",
        description="Remove a participant from combat (death, flee, surrender). If only one team remains, combat ends and the file is deleted.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (get this by reading the campaign://list resource first)"
                },
                "name": {
                    "type": "string",
                    "description": "Name of the participant to remove"
                },
                "reason": {
                    "type": "string",
                    "enum": ["death", "flee", "surrender"],
                    "description": "Why they're being removed: 'death' (killed), 'flee' (ran away), 'surrender' (gave up)"
                }
            },
            "required": ["campaign_id", "name"]
        }
    )


async def handle_remove_from_combat(arguments: dict) -> list[TextContent]:
    """Handle the remove_from_combat tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        name = arguments["name"]
        reason = arguments.get("reason", "death")  # Default to death if not specified

        # Load combat state via repository
        combat_state = _combat_repo.get_combat_state(campaign_id)
        if not combat_state:
            return [TextContent(type="text", text="No active combat found.")]

        if name not in combat_state["participants"]:
            return [TextContent(type="text", text=f"{name} is not in combat.")]

        # Remove participant
        del combat_state["participants"][name]

        # Build result message
        reason_messages = {
            "death": f"{name} has been slain!",
            "flee": f"{name} flees from combat!",
            "surrender": f"{name} surrenders!"
        }
        result_text = reason_messages.get(reason, f"{name} has left combat.")

        # Check if combat should end (only one team remains)
        remaining_teams = set(p.get("team") for p in combat_state["participants"].values())
        if len(remaining_teams) <= 1:
            # Sync remaining participants' health to NPC files if they exist
            npcs_index = _npc_repo.get_npc_index(campaign_id)

            for participant_name, participant_data in combat_state["participants"].items():
                participant_slug = slugify(participant_name)

                # Check if this participant is an NPC
                if participant_slug in npcs_index:
                    npc_data = _npc_repo.get_npc(campaign_id, participant_slug)
                    if npc_data:
                        npc_data["health"] = participant_data["health"]
                        npc_data["max_health"] = participant_data["max_health"]
                        _npc_repo.save_npc(campaign_id, participant_slug, npc_data)

            _combat_repo.delete_combat_state(campaign_id)
            result_text += "\nCombat has ended!"
        else:
            _combat_repo.save_combat_state(campaign_id, combat_state)

        return [TextContent(type="text", text=result_text)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error removing from combat: {str(e)}")]
