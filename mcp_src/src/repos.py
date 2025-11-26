"""Centralized repository instances for data persistence.

All tools should import repository instances from this module to ensure
consistency and avoid duplicate instantiation.
"""
from repository_json import (
    JsonCampaignRepository,
    JsonPlayerRepository,
    JsonNPCRepository,
    JsonBestiaryRepository,
    JsonCombatRepository,
)
from utils import slugify

# Global repository instances used throughout the application
campaign_repo = JsonCampaignRepository()
player_repo = JsonPlayerRepository()
npc_repo = JsonNPCRepository()
bestiary_repo = JsonBestiaryRepository()
combat_repo = JsonCombatRepository()


def sync_npc_to_combat(campaign_id: str, npc_slug: str, health: int) -> None:
    """Sync NPC health to combat state if they're an active participant.

    Call this after modifying NPC health outside of combat (e.g., heal_npc).
    """
    combat_state = combat_repo.get_combat_state(campaign_id)
    if not combat_state or "participants" not in combat_state:
        return

    # Find NPC in combat by matching slug
    for participant_name in combat_state["participants"]:
        if slugify(participant_name) == npc_slug:
            combat_state["participants"][participant_name]["health"] = health
            combat_repo.save_combat_state(campaign_id, combat_state)
            break


def resolve_npc_by_keyword(campaign_id: str, name: str) -> tuple[str, dict] | tuple[None, None]:
    """Resolve NPC by name or keyword.

    Args:
        campaign_id: The campaign ID
        name: NPC name or keyword to search for

    Returns:
        (npc_slug, npc_data) if found, (None, None) otherwise
    """
    # First try direct slug match
    npc_slug = slugify(name)
    npc_data = npc_repo.get_npc(campaign_id, npc_slug)
    if npc_data:
        return npc_slug, npc_data

    # Try keyword matching
    npcs_index = npc_repo.get_npc_index(campaign_id)
    for slug, npc_info in npcs_index.items():
        keywords = npc_info.get("keywords", [])
        if name.lower() in [k.lower() for k in keywords]:
            npc_data = npc_repo.get_npc(campaign_id, slug)
            if npc_data:
                return slug, npc_data

    return None, None
