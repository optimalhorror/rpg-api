import json
import random
import re

from mcp.types import Tool, TextContent

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import get_campaign_dir, health_description


def roll_dice(formula: str) -> int:
    """Roll dice from a formula like '1d6', '2d4+5', '20'."""
    formula = formula.lower().strip()

    # Just a number
    if formula.isdigit():
        return int(formula)

    # Parse XdY+Z or XdY-Z or XdY
    match = re.match(r'(\d+)?d(\d+)([+-]\d+)?', formula)
    if match:
        count = int(match.group(1) or 1)
        sides = int(match.group(2))
        modifier = int(match.group(3) or 0)

        total = sum(random.randint(1, sides) for _ in range(count))
        return total + modifier

    # Fallback: just return 20
    return 20


def get_participant_stats(campaign_dir: Path, name: str) -> dict:
    """Get participant stats: check NPC file first, then bestiary, then defaults."""
    from utils import slugify

    # 1. Check if existing NPC (load persisted health + weapons)
    npcs_index_file = campaign_dir / "npcs.json"
    if npcs_index_file.exists():
        npcs_index = json.loads(npcs_index_file.read_text())
        participant_slug = slugify(name)

        if participant_slug in npcs_index:
            npc_file = campaign_dir / npcs_index[participant_slug]["file"]
            if npc_file.exists():
                npc_data = json.loads(npc_file.read_text())
                return {
                    "health": npc_data.get("health", 20),
                    "max_health": npc_data.get("max_health", 20),
                    "weapons": npc_data.get("weapons", {})
                }

    # 2. Check bestiary for template (roll new stats)
    bestiary_file = campaign_dir / "bestiary.json"
    if bestiary_file.exists():
        bestiary = json.loads(bestiary_file.read_text())
        entry = bestiary.get(name.lower())

        if entry:
            max_health = roll_dice(entry["hp"])
            return {
                "health": max_health,
                "max_health": max_health,
                "weapons": entry.get("weapons", {})
            }

    # 3. Default stats
    return {
        "health": 20,
        "max_health": 20,
        "weapons": {}
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
                    "description": "Optional: Name of participant this attacker is allied with. If provided, attacker joins that participant's team. Only used when attacker is joining combat for the first time."
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

        campaign_dir = get_campaign_dir(campaign_id)
        combat_file = campaign_dir / "combat-current.json"

        # Load or create combat state
        if combat_file.exists():
            combat_state = json.loads(combat_file.read_text())
        else:
            combat_state = {"participants": {}, "next_team": 1}

        # Initialize participants with team assignment
        for participant in [attacker, target]:
            if participant not in combat_state["participants"]:
                stats = get_participant_stats(campaign_dir, participant)

                # Assign team
                if participant == attacker and allied_with:
                    # Copy team from allied participant
                    if allied_with in combat_state["participants"]:
                        stats["team"] = combat_state["participants"][allied_with]["team"]
                    else:
                        # Allied participant doesn't exist yet, assign new team
                        stats["team"] = combat_state.get("next_team", 1)
                        combat_state["next_team"] = stats["team"] + 1
                else:
                    # Assign new team
                    stats["team"] = combat_state.get("next_team", 1)
                    combat_state["next_team"] = stats["team"] + 1

                combat_state["participants"][participant] = stats

        # Simple combat: roll d20 for hit
        hit_roll = random.randint(1, 20)
        hit = hit_roll >= 6  # 75% hit chance

        result_lines = []

        if hit:
            # Get weapon damage from bestiary or default to 1d6
            attacker_data = combat_state["participants"][attacker]
            weapons = attacker_data.get("weapons", {})

            if weapon in weapons:
                damage = roll_dice(weapons[weapon])
            else:
                damage = random.randint(1, 6)  # Default 1d6
            hit_locations = ["head", "chest", "arm", "leg"]
            hit_location = random.choice(hit_locations)

            # Apply damage
            combat_state["participants"][target]["health"] -= damage
            combat_state["participants"][target]["health"] = max(0, combat_state["participants"][target]["health"])

            target_health = combat_state["participants"][target]["health"]
            target_max = combat_state["participants"][target]["max_health"]

            result_lines.append(f"{attacker} attacks {target} with {weapon}.")
            result_lines.append(f"{target} is hit in the {hit_location}.")

            # Check if target died
            if target_health <= 0:
                result_lines.append(f"{target} has been slain!")

                # Remove dead target from combat
                del combat_state["participants"][target]

                # Check if combat should end (only one team remains)
                remaining_teams = set(p.get("team", 1) for p in combat_state["participants"].values())
                if len(remaining_teams) <= 1:
                    # Sync remaining participants' health to NPC files if they exist
                    npcs_index_file = campaign_dir / "npcs.json"
                    if npcs_index_file.exists():
                        npcs_index = json.loads(npcs_index_file.read_text())

                        for participant_name, participant_data in combat_state["participants"].items():
                            from utils import slugify
                            participant_slug = slugify(participant_name)

                            # Check if this participant is an NPC
                            if participant_slug in npcs_index:
                                npc_file = campaign_dir / npcs_index[participant_slug]["file"]
                                if npc_file.exists():
                                    npc_data = json.loads(npc_file.read_text())
                                    npc_data["health"] = participant_data["health"]
                                    npc_data["max_health"] = participant_data["max_health"]
                                    npc_file.write_text(json.dumps(npc_data, indent=2))

                    combat_file.unlink(missing_ok=True)
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

        # Save combat state
        combat_file.write_text(json.dumps(combat_state, indent=2))

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

        campaign_dir = get_campaign_dir(campaign_id)
        combat_file = campaign_dir / "combat-current.json"

        if not combat_file.exists():
            return [TextContent(type="text", text="No active combat found.")]

        combat_state = json.loads(combat_file.read_text())

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
        remaining_teams = set(p.get("team", 1) for p in combat_state["participants"].values())
        if len(remaining_teams) <= 1:
            # Sync remaining participants' health to NPC files if they exist
            npcs_index_file = campaign_dir / "npcs.json"
            if npcs_index_file.exists():
                npcs_index = json.loads(npcs_index_file.read_text())

                for participant_name, participant_data in combat_state["participants"].items():
                    from utils import slugify
                    participant_slug = slugify(participant_name)

                    # Check if this participant is an NPC
                    if participant_slug in npcs_index:
                        npc_file = campaign_dir / npcs_index[participant_slug]["file"]
                        if npc_file.exists():
                            npc_data = json.loads(npc_file.read_text())
                            npc_data["health"] = participant_data["health"]
                            npc_data["max_health"] = participant_data["max_health"]
                            npc_file.write_text(json.dumps(npc_data, indent=2))

            combat_file.unlink(missing_ok=True)
            result_text += "\nCombat has ended!"
        else:
            combat_file.write_text(json.dumps(combat_state, indent=2))

        return [TextContent(type="text", text=result_text)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error removing from combat: {str(e)}")]
