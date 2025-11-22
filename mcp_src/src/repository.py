"""Repository pattern for data persistence abstraction."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pathlib import Path


class CampaignRepository(ABC):
    """Abstract interface for campaign data persistence."""

    @abstractmethod
    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get campaign data by ID."""
        pass

    @abstractmethod
    def save_campaign(self, campaign_id: str, data: Dict[str, Any]) -> None:
        """Save campaign data."""
        pass

    @abstractmethod
    def list_campaigns(self) -> Dict[str, str]:
        """List all campaigns. Returns {campaign_id: campaign_slug}."""
        pass

    @abstractmethod
    def get_campaign_dir(self, campaign_id: str) -> Path:
        """Get the directory path for a campaign."""
        pass


class NPCRepository(ABC):
    """Abstract interface for NPC data persistence."""

    @abstractmethod
    def get_npc(self, campaign_id: str, npc_slug: str) -> Optional[Dict[str, Any]]:
        """Get NPC data by slug."""
        pass

    @abstractmethod
    def save_npc(self, campaign_id: str, npc_slug: str, data: Dict[str, Any]) -> None:
        """Save NPC data."""
        pass

    @abstractmethod
    def get_npc_index(self, campaign_id: str) -> Dict[str, Any]:
        """Get NPC index. Returns {npc_slug: {keywords, file}}."""
        pass

    @abstractmethod
    def save_npc_index(self, campaign_id: str, index: Dict[str, Any]) -> None:
        """Save NPC index."""
        pass


class BestiaryRepository(ABC):
    """Abstract interface for bestiary data persistence."""

    @abstractmethod
    def get_bestiary(self, campaign_id: str) -> Dict[str, Any]:
        """Get full bestiary. Returns {creature_name: {threat_level, hp, weapons}}."""
        pass

    @abstractmethod
    def save_bestiary(self, campaign_id: str, data: Dict[str, Any]) -> None:
        """Save bestiary data."""
        pass

    @abstractmethod
    def get_entry(self, campaign_id: str, creature_name: str) -> Optional[Dict[str, Any]]:
        """Get single bestiary entry."""
        pass


class CombatRepository(ABC):
    """Abstract interface for combat state persistence."""

    @abstractmethod
    def get_combat_state(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get current combat state."""
        pass

    @abstractmethod
    def save_combat_state(self, campaign_id: str, data: Dict[str, Any]) -> None:
        """Save combat state."""
        pass

    @abstractmethod
    def delete_combat_state(self, campaign_id: str) -> None:
        """Delete combat state (combat ended)."""
        pass

    @abstractmethod
    def has_combat(self, campaign_id: str) -> bool:
        """Check if combat is active."""
        pass


class PlayerRepository(ABC):
    """Abstract interface for player data persistence."""

    @abstractmethod
    def get_player(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get player data."""
        pass

    @abstractmethod
    def save_player(self, campaign_id: str, data: Dict[str, Any]) -> None:
        """Save player data."""
        pass
