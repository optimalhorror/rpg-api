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

# Global repository instances used throughout the application
campaign_repo = JsonCampaignRepository()
player_repo = JsonPlayerRepository()
npc_repo = JsonNPCRepository()
bestiary_repo = JsonBestiaryRepository()
combat_repo = JsonCombatRepository()
