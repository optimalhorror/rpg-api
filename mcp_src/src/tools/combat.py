import random

from mcp.types import Tool, TextContent

from utils import get_campaign_dir, health_description, slugify, roll_dice, damage_descriptor, threat_level_to_hit_chance, format_list_from_dict, err_not_found, err_already_exists, err_missing, err_invalid
from repos import npc_repo, bestiary_repo, combat_repo, campaign_repo, resolve_npc_by_keyword


def resolve_participant_name(campaign_id: str, name: str) -> tuple[str, bool]:
    """Resolve participant name using NPC keywords only. Returns (full_name, is_valid).

    Note: Bestiary entries are templates, not actual enemies. Use spawn_enemy to create
    combat instances from bestiary templates.
    """
    # Try NPC resolution (by name or keyword)
    _, npc_data = resolve_npc_by_keyword(campaign_id, name)
    if npc_data:
        return (npc_data["name"], True)

    # Not found - bestiary entries require spawn_enemy first
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


def is_participant_player(campaign_id: str, name: str) -> bool:
    """Check if a participant is the player character.

    Uses two methods to ensure player is never accidentally deleted:
    1. Check campaign.json for player.name match
    2. Check if NPC file has 'player' keyword
    """
    # Method 1: Check campaign.json player name
    campaign_data = campaign_repo.get_campaign(campaign_id)
    if campaign_data:
        player_name = campaign_data.get("player", {}).get("name", "")
        if player_name and name.lower() == player_name.lower():
            return True

    # Method 2: Check NPC keywords for "player" (defensive check)
    participant_slug = slugify(name)
    npc_data = npc_repo.get_npc(campaign_id, participant_slug)
    if npc_data:
        keywords = npc_data.get("keywords", [])
        if "player" in [k.lower() for k in keywords]:
            return True

    return False


def sync_all_participants_health(campaign_id: str, combat_state: dict) -> None:
    """Sync all remaining participants' health to NPC files."""
    for participant_name, participant_data in combat_state["participants"].items():
        sync_npc_health(
            campaign_id,
            participant_name,
            participant_data["health"],
            participant_data["max_health"]
        )


def end_combat_for_player(campaign_id: str, combat_state: dict) -> str:
    """Handle combat ending when player leaves. Returns end message."""
    sync_all_participants_health(campaign_id, combat_state)
    combat_repo.delete_combat_state(campaign_id)
    return "\nCombat has ended!"


def get_participant_stats(campaign_id: str, name: str) -> dict | None:
    """Get participant stats: check NPC file first (with keyword matching), then bestiary.

    Returns None if participant not found (caller should handle this).
    """
    # 1. Check if existing NPC using keyword matching (e.g., "player", "you", etc.)
    _, npc_data = resolve_npc_by_keyword(campaign_id, name)
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

    # Not found
    return None


def handle_participant_death(campaign_id: str, participant_name: str) -> None:
    """Handle participant death: set HP to 0 and delete NPC file (unless player).

    Args:
        campaign_id: The campaign ID
        participant_name: Name of the participant who died
    """
    participant_slug = slugify(participant_name)
    npc_data = npc_repo.get_npc(campaign_id, participant_slug)

    if npc_data:
        # Set health to 0
        npc_data["health"] = 0
        npc_repo.save_npc(campaign_id, participant_slug, npc_data)

        # Delete NPC file for non-player deaths
        if not is_participant_player(campaign_id, participant_name):
            npc_repo.delete_npc(campaign_id, participant_slug)


def check_and_end_combat(campaign_id: str, combat_state: dict) -> tuple[bool, str]:
    """Check if combat should end (only one team remains) and handle cleanup.

    Returns:
        (combat_ended, message): True if combat ended with message, False with empty string otherwise.
    """
    remaining_teams = set(p.get("team") for p in combat_state["participants"].values())
    if len(remaining_teams) <= 1:
        sync_all_participants_health(campaign_id, combat_state)
        combat_repo.delete_combat_state(campaign_id)
        return True, "\nCombat has ended!"
    else:
        combat_repo.save_combat_state(campaign_id, combat_state)
        return False, ""


def find_item_case_insensitive(items: dict, key: str) -> tuple[str | None, any]:
    """Find an item in a dictionary using case-insensitive key matching.

    Returns:
        (actual_key, value) if found, (None, None) otherwise
    """
    key_lower = key.lower()
    for item_key, item_value in items.items():
        if item_key.lower() == key_lower:
            return (item_key, item_value)
    return (None, None)


def resolve_weapon(campaign_id: str, attacker_name: str, attacker_data: dict, weapon: str) -> tuple[str | None, bool, str | None]:
    """Resolve weapon damage formula for an attacker.

    Args:
        campaign_id: The campaign ID
        attacker_name: Resolved attacker name
        attacker_data: Attacker's combat state data (for bestiary_template lookup)
        weapon: Weapon name to resolve

    Returns:
        (damage_formula, is_improvised, error) - error is None on success, message on failure
    """
    attacker_slug = slugify(attacker_name)
    npc_data = npc_repo.get_npc(campaign_id, attacker_slug)

    # For spawned enemies, use stored template; otherwise use participant name
    bestiary_lookup = attacker_data.get("bestiary_template", attacker_name)
    bestiary_entry = bestiary_repo.get_entry(campaign_id, bestiary_lookup)

    # 1. NPCs with inventory - check real-time inventory
    if npc_data and "inventory" in npc_data:
        inventory = npc_data["inventory"]
        items = inventory.get("items", {})

        # Case-insensitive weapon lookup
        _, item = find_item_case_insensitive(items, weapon)
        if item:
            if item.get("weapon") and item.get("damage"):
                return (item["damage"], False, None)
            else:
                # Item exists but not a weapon - improvised
                return ("1d4", True, None)
        else:
            # Check for unarmed attack
            unarmed_keywords = ["fists", "fist", "punch", "kick", "unarmed", "bare hands"]
            if weapon.lower() in unarmed_keywords:
                return ("1d4", False, None)
            else:
                items_list = format_list_from_dict(items, "none (try 'fists' for unarmed)")
                return (None, False, err_missing(attacker_name, weapon, items_list))

    # 2. Bestiary monsters - use their defined weapons
    elif bestiary_entry:
        bestiary_weapons = bestiary_entry.get("weapons", {})
        # Case-insensitive weapon lookup
        _, damage = find_item_case_insensitive(bestiary_weapons, weapon)
        if damage:
            return (damage, False, None)
        else:
            weapons_list = format_list_from_dict(bestiary_weapons)
            return (None, False, err_missing(attacker_name, weapon, weapons_list))

    # 3. Unknown participants
    else:
        return (None, False, err_invalid(f"'{attacker_name}' is not a valid participant.", "Use create_npc or create_bestiary_entry first."))


def get_spawn_enemy_tool() -> Tool:
    """Return the spawn_enemy tool definition."""
    return Tool(
        name="spawn_enemy",
        description="Spawn a combat enemy from a bestiary template with a custom name. Use this to create multiple instances of the same creature type. Spawned enemies exist only in combat and are removed when combat ends or they die.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (use list_campaigns to get this)"
                },
                "name": {
                    "type": "string",
                    "description": "Custom name for this enemy instance"
                },
                "bestiary_template": {
                    "type": "string",
                    "description": "Bestiary entry to use as template for stats"
                },
                "team": {
                    "type": "string",
                    "description": "Optional: Team name for this enemy. Enemies on the same team won't fight each other. Defaults to enemy's name."
                }
            },
            "required": ["campaign_id", "name", "bestiary_template"]
        }
    )


async def handle_spawn_enemy(arguments: dict) -> list[TextContent]:
    """Handle the spawn_enemy tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        name = arguments["name"]
        bestiary_template = arguments["bestiary_template"]
        team = arguments.get("team", name)

        # Verify bestiary template exists
        entry = bestiary_repo.get_entry(campaign_id, bestiary_template)
        if not entry:
            return [TextContent(
                type="text",
                text=err_not_found("Bestiary template", bestiary_template, "Use create_bestiary_entry first.")
            )]

        # Load or create combat state
        combat_state = combat_repo.get_combat_state(campaign_id)
        if not combat_state:
            combat_state = {"participants": {}}

        # Check if name already exists in combat
        if name in combat_state["participants"]:
            return [TextContent(
                type="text",
                text=err_already_exists("Combatant", name, "Use a different name.")
            )]

        # Get stats from bestiary template
        stats = get_participant_stats(campaign_id, bestiary_template)
        if not stats:
            return [TextContent(
                type="text",
                text=err_not_found("Bestiary template stats", bestiary_template, "Template may be corrupted.")
            )]
        stats["team"] = team
        stats["bestiary_template"] = bestiary_template  # Store template for weapon lookup

        # Add to combat
        combat_state["participants"][name] = stats
        combat_repo.save_combat_state(campaign_id, combat_state)

        return [TextContent(
            type="text",
            text=f"{name} enters the fray! (Template: {bestiary_template}, Team: {team})"
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Error spawning enemy: {str(e)}")]


def get_attack_tool() -> Tool:
    """Return the attack tool definition."""
    return Tool(
        name="attack",
        description="Perform an attack action between NPCs and/or spawned enemies. Participants must already exist: NPCs (created with create_npc), bestiary creatures (direct match), or spawned enemies (created with spawn_enemy). Returns human-readable combat results including hit/miss, damage description, and health states. If no weapon is specified, attacker uses unarmed combat (1d4 damage). Note: Attacking a teammate is betrayal - attacker switches to solo team.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (use list_campaigns to get this)"
                },
                "attacker": {
                    "type": "string",
                    "description": "Attacker name. Can be an NPC name/keyword or a spawned enemy name."
                },
                "target": {
                    "type": "string",
                    "description": "Target name. Can be an NPC name/keyword or a spawned enemy name."
                },
                "weapon": {
                    "type": "string",
                    "description": "Optional: Weapon name from attacker's inventory or bestiary. If omitted, uses unarmed combat (1d4 damage)."
                },
                "team": {
                    "type": "string",
                    "description": "Optional: Team name for the attacker. If not specified, keeps current team (or solo if new to combat)."
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

        # Resolve attacker: check combat first, then NPC/bestiary
        attacker_resolved = None
        for participant_name in combat_state.get("participants", {}).keys():
            if slugify(participant_name) == slugify(attacker):
                attacker_resolved = participant_name
                break

        if not attacker_resolved:
            attacker_resolved, attacker_valid = resolve_participant_name(campaign_id, attacker)
            if not attacker_valid:
                return [TextContent(
                    type="text",
                    text=err_not_found("Participant", attacker, "Use NPC name/keyword or spawn_enemy first.")
                )]

        # Resolve target: check combat first, then NPC/bestiary
        target_resolved = None
        for participant_name in combat_state.get("participants", {}).keys():
            if slugify(participant_name) == slugify(target):
                target_resolved = participant_name
                break

        if not target_resolved:
            target_resolved, target_valid = resolve_participant_name(campaign_id, target)
            if not target_valid:
                return [TextContent(
                    type="text",
                    text=err_not_found("Participant", target, "Use NPC name/keyword or spawn_enemy first.")
                )]

        # Validate weapon BEFORE adding participants to combat
        # For existing participants, use their combat data; for new ones, use empty dict
        # (resolve_weapon will check NPC inventory first, then bestiary by name)
        attacker_data_for_validation = combat_state["participants"].get(attacker_resolved, {})
        _, _, weapon_error = resolve_weapon(campaign_id, attacker_resolved, attacker_data_for_validation, weapon)
        if weapon_error:
            return [TextContent(type="text", text=weapon_error)]

        # Initialize participants if not in combat yet
        for participant, resolved_name in [(attacker, attacker_resolved), (target, target_resolved)]:
            if resolved_name not in combat_state["participants"]:
                stats = get_participant_stats(campaign_id, resolved_name)
                if not stats:
                    return [TextContent(
                        type="text",
                        text=err_not_found("Participant", resolved_name, "NPC may have been deleted.")
                    )]

                # Assign team
                if participant == attacker:
                    stats["team"] = team_name if team_name else resolved_name
                else:
                    stats["team"] = resolved_name

                combat_state["participants"][resolved_name] = stats

        # Update attacker's team on each attack (allows team switching)
        if team_name:
            combat_state["participants"][attacker_resolved]["team"] = team_name

        # Simple combat: roll d100 for hit, using attacker's hit_chance percentage
        attacker_data = combat_state["participants"][attacker_resolved]
        hit_chance = attacker_data.get("hit_chance", 50)
        hit_roll = roll_dice("1d100")
        hit = hit_roll <= hit_chance

        result_lines = []

        if hit:
            # Check for self-attack or team betrayal
            if attacker_resolved == target_resolved:
                result_lines.append(f"{attacker_resolved} was their own worst enemy all along.")
            elif check_team_betrayal(combat_state, attacker_resolved, target_resolved):
                result_lines.append(f"{attacker_resolved} has betrayed their team!")

            # Resolve weapon damage (already validated early, so no error check needed)
            damage_formula, is_improvised, _ = resolve_weapon(
                campaign_id, attacker_resolved, attacker_data, weapon
            )

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

                # If player died, end combat entirely
                if is_participant_player(campaign_id, target_resolved):
                    result_lines.append(end_combat_for_player(campaign_id, combat_state))
                else:
                    # Check if combat should end (only one team remains)
                    combat_ended, end_msg = check_and_end_combat(campaign_id, combat_state)
                    if combat_ended:
                        result_lines.append(end_msg)
            else:
                result_lines.append(f"{target_resolved} is {health_description(target_health, target_max)}.")
                # Save combat state since combat continues
                combat_repo.save_combat_state(campaign_id, combat_state)
        else:
            # Miss - but still check for self-attack or team betrayal
            if attacker_resolved == target_resolved:
                result_lines.append(f"{attacker_resolved} was their own worst enemy all along.")
            elif check_team_betrayal(combat_state, attacker_resolved, target_resolved):
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

        # If death, handle death (sets HP to 0, deletes NPC file if not player)
        if reason == "death":
            handle_participant_death(campaign_id, name)

        # Check if removed participant is the player
        player_leaving = is_participant_player(campaign_id, name)

        # Remove participant from combat
        del combat_state["participants"][name]

        # Build result message
        reason_messages = {
            "death": f"{name} has been slain!",
            "flee": f"{name} flees from combat!",
            "surrender": f"{name} surrenders!"
        }
        result_text = reason_messages.get(reason, f"{name} has left combat.")

        # If player left combat, end combat entirely
        if player_leaving:
            result_text += end_combat_for_player(campaign_id, combat_state)
        else:
            # Check if combat should end (only one team remains)
            combat_ended, end_msg = check_and_end_combat(campaign_id, combat_state)
            if combat_ended:
                result_text += end_msg

        return [TextContent(type="text", text=result_text)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error removing from combat: {str(e)}")]
