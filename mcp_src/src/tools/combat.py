import random

from mcp.types import Tool, TextContent

from utils import get_campaign_dir, health_description, slugify, roll_dice, damage_descriptor, threat_level_to_hit_chance
from repos import npc_repo, bestiary_repo, combat_repo, campaign_repo


def resolve_participant_name(campaign_id: str, name: str) -> tuple[str, bool]:
    """Resolve participant name using NPC keywords. Returns (full_name, is_valid)."""
    # First check if exact slug match exists in NPCs
    participant_slug = slugify(name)
    npc_data = npc_repo.get_npc(campaign_id, participant_slug)
    if npc_data:
        return (npc_data["name"], True)

    # Check NPC index for keyword matches
    npcs_index = npc_repo.get_npc_index(campaign_id)
    for npc_slug, npc_info in npcs_index.items():
        keywords = npc_info.get("keywords", [])
        # Match if name matches any keyword (case-insensitive)
        if name.lower() in [k.lower() for k in keywords]:
            npc_data = npc_repo.get_npc(campaign_id, npc_slug)
            if npc_data:
                return (npc_data["name"], True)

    # Check bestiary for exact match
    entry = bestiary_repo.get_entry(campaign_id, name)
    if entry:
        return (name, True)

    # Not found
    return (name, False)


def check_team_betrayal(combat_state: dict, attacker_resolved: str, target_resolved: str) -> bool:
    """Check if attacker is attacking their own team. If so, switch them to solo team.

    Returns True if betrayal occurred, False otherwise.
    """
    attacker_team = combat_state["participants"][attacker_resolved].get("team")
    target_team = combat_state["participants"][target_resolved].get("team")

    if attacker_team == target_team:
        # Betrayal! Switch attacker to solo team
        combat_state["participants"][attacker_resolved]["team"] = attacker_resolved
        return True

    return False


def sync_npc_health(campaign_id: str, participant_name: str, health: int, max_health: int) -> None:
    """Sync combat health back to NPC file if participant is an NPC."""
    participant_slug = slugify(participant_name)
    npc_data = npc_repo.get_npc(campaign_id, participant_slug)

    if npc_data:
        npc_data["health"] = health
        npc_data["max_health"] = max_health
        npc_repo.save_npc(campaign_id, participant_slug, npc_data)


def get_participant_stats(campaign_id: str, name: str) -> dict:
    """Get participant stats: check NPC file first, then bestiary.

    Note: Participants are validated before calling this function via resolve_participant_name(),
    so this function should always find either NPC or bestiary data.
    """
    participant_slug = slugify(name)

    # 1. Check if existing NPC (load persisted health + hit_chance)
    npc_data = npc_repo.get_npc(campaign_id, participant_slug)
    if npc_data:
        return {
            "health": npc_data.get("health", 20),
            "max_health": npc_data.get("max_health", 20),
            "hit_chance": npc_data.get("hit_chance", 50)
        }

    # 2. Check bestiary for template (roll new stats + map threat to hit_chance)
    entry = bestiary_repo.get_entry(campaign_id, name)
    if entry:
        max_health = roll_dice(entry["hp"])
        threat_level = entry.get("threat_level", "moderate")
        hit_chance = threat_level_to_hit_chance(threat_level)
        return {
            "health": max_health,
            "max_health": max_health,
            "hit_chance": hit_chance
        }


def handle_participant_death(campaign_id: str, participant_name: str) -> None:
    """Handle participant death: delete NPC file unless it's the player character.

    Args:
        campaign_id: The campaign ID
        participant_name: Name of the participant who died
    """
    # Check if dead participant is the player character
    campaign_data = campaign_repo.get_campaign(campaign_id)
    player_name = campaign_data.get("player", {}).get("name", "") if campaign_data else ""
    is_player = participant_name.lower() == player_name.lower()

    # Delete NPC file for non-player deaths
    participant_slug = slugify(participant_name)
    npc_data = npc_repo.get_npc(campaign_id, participant_slug)
    if not is_player and npc_data:
        npc_repo.delete_npc(campaign_id, participant_slug)


def check_and_end_combat(campaign_id: str, combat_state: dict) -> tuple[bool, str]:
    """Check if combat should end (only one team remains) and handle cleanup.

    Returns:
        (combat_ended, message): True if combat ended with message, False with empty string otherwise.
    """
    remaining_teams = set(p.get("team") for p in combat_state["participants"].values())
    if len(remaining_teams) <= 1:
        # Sync remaining participants' health to NPC files if they exist
        for participant_name, participant_data in combat_state["participants"].items():
            sync_npc_health(
                campaign_id,
                participant_name,
                participant_data["health"],
                participant_data["max_health"]
            )

        combat_repo.delete_combat_state(campaign_id)
        return True, "\nCombat has ended!"
    else:
        combat_repo.save_combat_state(campaign_id, combat_state)
        return False, ""


def get_attack_tool() -> Tool:
    """Return the attack tool definition."""
    return Tool(
        name="attack",
        description="Perform an attack action between NPCs and/or monsters (bestiary entries). Participants can be NPCs (created with create_npc) or bestiary creatures (created with create_bestiary_entry). Returns human-readable combat results including hit/miss, damage description, and health states. If no weapon is specified, attacker uses unarmed combat (1d4 damage). Use list_campaigns to get campaign_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (use list_campaigns to get this)"
                },
                "attacker": {
                    "type": "string",
                    "description": "Identifier or keyword for the attacker. Can be an NPC name/keyword (e.g., 'player', 'Steve', 'blacksmith') or a bestiary creature type (e.g., 'goblin', 'wolf', 'skeleton')."
                },
                "target": {
                    "type": "string",
                    "description": "Identifier or keyword for the target being attacked. Can be an NPC name/keyword or a bestiary creature type."
                },
                "weapon": {
                    "type": "string",
                    "description": "Optional: Weapon being used (e.g., 'sword', 'dagger'). If omitted, uses unarmed combat (fists, 1d4 damage)."
                },
                "team": {
                    "type": "string",
                    "description": "Optional: Team name for the attacker (e.g., 'guards', 'bandits', 'party'). If not specified, attacker fights solo on a team named after themselves. Can be any team name - doesn't need to match an existing participant."
                }
            },
            "required": ["campaign_id", "attacker", "target"]
        }
    )


async def handle_attack(arguments: dict) -> list[TextContent]:
    """Handle the attack tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        attacker = arguments["attacker"]
        target = arguments["target"]
        weapon = arguments.get("weapon")  # Optional - defaults to unarmed if not provided
        team_name = arguments.get("team")

        # If no weapon specified, default to unarmed combat
        if not weapon:
            weapon = "unarmed"

        # Load or create combat state via repository
        combat_state = combat_repo.get_combat_state(campaign_id)
        if not combat_state:
            combat_state = {"participants": {}}

        # Resolve participant names (check if already in combat first, then resolve via keywords)
        attacker_resolved = None
        target_resolved = None

        # Check if attacker already in combat (use existing name)
        for participant_name in combat_state.get("participants", {}).keys():
            if slugify(participant_name) == slugify(attacker):
                attacker_resolved = participant_name
                break

        # If not in combat, resolve via keywords/NPC/bestiary
        if not attacker_resolved:
            attacker_resolved, attacker_valid = resolve_participant_name(campaign_id, attacker)
            if not attacker_valid:
                return [TextContent(
                    type="text",
                    text=f"Error: {attacker} is not a valid participant. Attackers must be either NPCs (use create_npc) or bestiary creatures (use create_bestiary_entry)."
                )]

        # Check if target already in combat (use existing name)
        for participant_name in combat_state.get("participants", {}).keys():
            if slugify(participant_name) == slugify(target):
                target_resolved = participant_name
                break

        # If not in combat, resolve via keywords/NPC/bestiary
        if not target_resolved:
            target_resolved, target_valid = resolve_participant_name(campaign_id, target)
            if not target_valid:
                return [TextContent(
                    type="text",
                    text=f"Error: {target} is not a valid target. Targets must be either NPCs (use create_npc) or bestiary creatures (use create_bestiary_entry)."
                )]

        # Initialize participants with team assignment (using resolved names)
        for participant, resolved_name in [(attacker, attacker_resolved), (target, target_resolved)]:
            if resolved_name not in combat_state["participants"]:
                stats = get_participant_stats(campaign_id, resolved_name)

                # Assign team (string-based)
                if participant == attacker:
                    # Attacker uses provided team name or defaults to their resolved name
                    stats["team"] = team_name if team_name else resolved_name
                else:
                    # Target always defaults to their own team (use resolved name)
                    stats["team"] = resolved_name

                combat_state["participants"][resolved_name] = stats

        # Update attacker's team on each attack (allows team switching)
        if team_name:
            combat_state["participants"][attacker_resolved]["team"] = team_name

        # Simple combat: roll d20 for hit, using attacker's hit_chance
        attacker_data = combat_state["participants"][attacker_resolved]
        hit_chance = attacker_data.get("hit_chance", 50)
        hit_roll = random.randint(1, 20)
        # Convert hit_chance percentage to d20 threshold (e.g., 50% = >= 11, 75% = >= 6)
        hit_threshold = 21 - int(hit_chance * 20 / 100)
        hit = hit_roll >= hit_threshold

        result_lines = []

        if hit:
            # Check for team betrayal - attacking your own team
            if check_team_betrayal(combat_state, attacker_resolved, target_resolved):
                result_lines.append(f"{attacker_resolved} has betrayed their team!")

            # Get weapon damage: check real-time inventory (NPCs) and bestiary (monsters)
            attacker_slug = slugify(attacker_resolved)
            damage_formula = None
            is_improvised = False

            # Check if attacker is an NPC or monster
            npc_data = npc_repo.get_npc(campaign_id, attacker_slug)
            bestiary_entry = bestiary_repo.get_entry(campaign_id, attacker_resolved)

            # 1. NPCs with inventory - check real-time inventory (not combat state)
            if npc_data and "inventory" in npc_data:
                inventory = npc_data["inventory"]
                items = inventory.get("items", {})

                if weapon in items:
                    item = items[weapon]
                    # Check if it's a proper weapon
                    if item.get("weapon") and item.get("damage"):
                        damage_formula = item["damage"]
                    else:
                        # Item exists but not a weapon - allow as improvised (1d4)
                        damage_formula = "1d4"
                        is_improvised = True
                else:
                    # Check if unarmed attack (fists, punch, kick, etc.)
                    unarmed_keywords = ["fists", "fist", "punch", "kick", "unarmed", "bare hands"]
                    if weapon.lower() in unarmed_keywords:
                        # Allow unarmed attacks with minimal damage
                        damage_formula = "1d4"
                        is_improvised = False  # Not improvised, just weak
                    else:
                        # Item doesn't exist in inventory
                        available_items = list(items.keys()) if items else []
                        items_list = ", ".join(available_items) if available_items else "none (try 'fists' for unarmed)"
                        return [TextContent(
                            type="text",
                            text=f"Error: {attacker_resolved} doesn't have '{weapon}' in inventory. Available items: {items_list}"
                        )]

            # 2. Bestiary monsters - use their defined weapons only
            elif bestiary_entry:
                bestiary_weapons = bestiary_entry.get("weapons", {})
                if weapon in bestiary_weapons:
                    damage_formula = bestiary_weapons[weapon]
                else:
                    available_weapons = list(bestiary_weapons.keys()) if bestiary_weapons else []
                    weapons_list = ", ".join(available_weapons) if available_weapons else "none"
                    return [TextContent(
                        type="text",
                        text=f"Error: {attacker_resolved} doesn't have '{weapon}'. Available weapons: {weapons_list}"
                    )]

            # 3. Unknown participants - ERROR (must be NPC or bestiary entry)
            else:
                return [TextContent(
                    type="text",
                    text=f"Error: {attacker_resolved} is not a valid participant. Attackers must be either NPCs (use create_npc) or bestiary creatures (use create_bestiary_entry)."
                )]

            # Roll damage
            damage = roll_dice(damage_formula)

            hit_locations = ["head", "chest", "arm", "leg"]
            hit_location = random.choice(hit_locations)

            # Apply damage
            combat_state["participants"][target_resolved]["health"] -= damage
            combat_state["participants"][target_resolved]["health"] = max(0, combat_state["participants"][target_resolved]["health"])

            target_health = combat_state["participants"][target_resolved]["health"]
            target_max = combat_state["participants"][target_resolved]["max_health"]

            # Sync health to NPC file if target is an NPC (real-time tracking)
            sync_npc_health(campaign_id, target_resolved, target_health, target_max)

            # Narrative output (hide mechanics)
            damage_desc = damage_descriptor(damage, damage_formula)
            weapon_desc = f"improvised weapon ({weapon})" if is_improvised else weapon
            result_lines.append(f"{attacker_resolved} attacks {target_resolved} with {weapon_desc}.")
            result_lines.append(f"The attack {damage_desc} into the {hit_location}.")

            # Check if target died
            if target_health <= 0:
                result_lines.append(f"{target_resolved} has been slain!")

                # Handle death: delete NPC file (unless player)
                handle_participant_death(campaign_id, target_resolved)

                # Remove dead target from combat
                del combat_state["participants"][target_resolved]

                # Check if combat should end and handle cleanup
                combat_ended, end_msg = check_and_end_combat(campaign_id, combat_state)
                if combat_ended:
                    result_lines.append(end_msg)
            else:
                result_lines.append(f"{target_resolved} is {health_description(target_health, target_max)}.")
                # Save combat state since combat continues
                combat_repo.save_combat_state(campaign_id, combat_state)
        else:
            # Miss - but still check for team betrayal
            if check_team_betrayal(combat_state, attacker_resolved, target_resolved):
                result_lines.append(f"{attacker_resolved} has betrayed their team!")

            result_lines.append(f"{attacker_resolved} attacks {target_resolved} with {weapon}.")
            result_lines.append(f"{target_resolved} dodges the attack.")

            # Show target health even on miss
            if target_resolved in combat_state["participants"]:
                target_health = combat_state["participants"][target_resolved]["health"]
                target_max = combat_state["participants"][target_resolved]["max_health"]
                result_lines.append(f"{target_resolved} is {health_description(target_health, target_max)}.")

            # Save combat state since combat continues
            combat_repo.save_combat_state(campaign_id, combat_state)

        return [TextContent(type="text", text="\n".join(result_lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error in attack: {str(e)}")]


def get_remove_from_combat_tool() -> Tool:
    """Return the remove_from_combat tool definition."""
    return Tool(
        name="remove_from_combat",
        description="Remove an NPC or monster participant from combat (death, flee, surrender). If 'death' is chosen, the NPC file is deleted (unless it's the player). If only one team remains after removal, combat ends and the file is deleted.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (use list_campaigns to get this)"
                },
                "name": {
                    "type": "string",
                    "description": "Name of the participant to remove. Must match an active combat participant (use get_combat_status to see current participants)."
                },
                "reason": {
                    "type": "string",
                    "enum": ["death", "flee", "surrender"],
                    "description": "Why they're being removed: 'death' (killed, deletes NPC file), 'flee' (ran away), 'surrender' (gave up)"
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
        combat_state = combat_repo.get_combat_state(campaign_id)
        if not combat_state:
            return [TextContent(type="text", text="There's no active combat.")]

        if name not in combat_state["participants"]:
            return [TextContent(type="text", text=f"{name} is not in combat.")]

        # If death, delete NPC file (but not player)
        if reason == "death":
            handle_participant_death(campaign_id, name)

        # Remove participant from combat
        del combat_state["participants"][name]

        # Build result message
        reason_messages = {
            "death": f"{name} has been slain!",
            "flee": f"{name} flees from combat!",
            "surrender": f"{name} surrenders!"
        }
        result_text = reason_messages.get(reason, f"{name} has left combat.")

        # Check if combat should end and handle cleanup
        combat_ended, end_msg = check_and_end_combat(campaign_id, combat_state)
        if combat_ended:
            result_text += end_msg

        return [TextContent(type="text", text=result_text)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error removing from combat: {str(e)}")]
