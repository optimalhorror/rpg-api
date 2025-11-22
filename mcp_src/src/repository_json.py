"""JSON file-based repository implementations."""
import json
from pathlib import Path
from typing import Optional, Dict, Any

from repository import (
    CampaignRepository,
    NPCRepository,
    BestiaryRepository,
    CombatRepository,
    PlayerRepository,
)
from utils import get_campaign_dir, load_campaign_list, CAMPAIGNS_DIR, slugify


class JsonCampaignRepository(CampaignRepository):
    """JSON file-based campaign persistence."""

    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        campaign_list = load_campaign_list()
        campaign_slug = campaign_list.get(campaign_id)
        if not campaign_slug:
            return None

        campaign_file = CAMPAIGNS_DIR / campaign_slug / "campaign.json"
        if not campaign_file.exists():
            return None

        return json.loads(campaign_file.read_text())

    def save_campaign(self, campaign_id: str, data: Dict[str, Any]) -> None:
        campaign_list = load_campaign_list()
        campaign_slug = campaign_list.get(campaign_id)
        if not campaign_slug:
            raise ValueError(f"Campaign not found: {campaign_id}")

        campaign_file = CAMPAIGNS_DIR / campaign_slug / "campaign.json"
        campaign_file.write_text(json.dumps(data, indent=2))

    def list_campaigns(self) -> Dict[str, str]:
        return load_campaign_list()

    def get_campaign_dir(self, campaign_id: str) -> Path:
        return get_campaign_dir(campaign_id)


class JsonNPCRepository(NPCRepository):
    """JSON file-based NPC persistence."""

    def get_npc(self, campaign_id: str, npc_slug: str) -> Optional[Dict[str, Any]]:
        campaign_dir = get_campaign_dir(campaign_id)
        npc_file = campaign_dir / f"npc-{npc_slug}.json"

        if not npc_file.exists():
            return None

        return json.loads(npc_file.read_text())

    def save_npc(self, campaign_id: str, npc_slug: str, data: Dict[str, Any]) -> None:
        campaign_dir = get_campaign_dir(campaign_id)
        npc_file = campaign_dir / f"npc-{npc_slug}.json"
        npc_file.write_text(json.dumps(data, indent=2))

    def get_npc_index(self, campaign_id: str) -> Dict[str, Any]:
        campaign_dir = get_campaign_dir(campaign_id)
        npcs_index_file = campaign_dir / "npcs.json"

        if not npcs_index_file.exists():
            return {}

        return json.loads(npcs_index_file.read_text())

    def save_npc_index(self, campaign_id: str, index: Dict[str, Any]) -> None:
        campaign_dir = get_campaign_dir(campaign_id)
        npcs_index_file = campaign_dir / "npcs.json"
        npcs_index_file.write_text(json.dumps(index, indent=2))


class JsonBestiaryRepository(BestiaryRepository):
    """JSON file-based bestiary persistence."""

    def get_bestiary(self, campaign_id: str) -> Dict[str, Any]:
        campaign_dir = get_campaign_dir(campaign_id)
        bestiary_file = campaign_dir / "bestiary.json"

        if not bestiary_file.exists():
            return {}

        return json.loads(bestiary_file.read_text())

    def save_bestiary(self, campaign_id: str, data: Dict[str, Any]) -> None:
        campaign_dir = get_campaign_dir(campaign_id)
        bestiary_file = campaign_dir / "bestiary.json"
        bestiary_file.write_text(json.dumps(data, indent=2))

    def get_entry(self, campaign_id: str, creature_name: str) -> Optional[Dict[str, Any]]:
        bestiary = self.get_bestiary(campaign_id)
        return bestiary.get(creature_name.lower())


class JsonCombatRepository(CombatRepository):
    """JSON file-based combat state persistence."""

    def get_combat_state(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        campaign_dir = get_campaign_dir(campaign_id)
        combat_file = campaign_dir / "combat-current.json"

        if not combat_file.exists():
            return None

        return json.loads(combat_file.read_text())

    def save_combat_state(self, campaign_id: str, data: Dict[str, Any]) -> None:
        campaign_dir = get_campaign_dir(campaign_id)
        combat_file = campaign_dir / "combat-current.json"
        combat_file.write_text(json.dumps(data, indent=2))

    def delete_combat_state(self, campaign_id: str) -> None:
        campaign_dir = get_campaign_dir(campaign_id)
        combat_file = campaign_dir / "combat-current.json"
        combat_file.unlink(missing_ok=True)

    def has_combat(self, campaign_id: str) -> bool:
        campaign_dir = get_campaign_dir(campaign_id)
        combat_file = campaign_dir / "combat-current.json"
        return combat_file.exists()


class JsonPlayerRepository(PlayerRepository):
    """JSON file-based player data persistence."""

    def get_player(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        campaign_dir = get_campaign_dir(campaign_id)
        player_file = campaign_dir / "player.json"

        if not player_file.exists():
            return None

        return json.loads(player_file.read_text())

    def save_player(self, campaign_id: str, data: Dict[str, Any]) -> None:
        campaign_dir = get_campaign_dir(campaign_id)
        player_file = campaign_dir / "player.json"
        player_file.write_text(json.dumps(data, indent=2))
