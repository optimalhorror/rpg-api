"""Integration tests for repository and tool handlers."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

# We'll patch utils module paths before importing repos
import utils


@pytest.fixture
def campaign_dir(tmp_path):
    """Create a temporary campaign structure for testing."""
    campaigns_dir = tmp_path / "campaigns"
    campaigns_dir.mkdir()

    # Create a test campaign
    test_campaign_dir = campaigns_dir / "test-campaign"
    test_campaign_dir.mkdir()

    # Create campaign list
    list_file = campaigns_dir / "list.json"
    list_file.write_text(json.dumps({"test-123": "test-campaign"}))

    # Create basic campaign.json
    campaign_file = test_campaign_dir / "campaign.json"
    campaign_file.write_text(json.dumps({
        "name": "Test Campaign",
        "description": "A test campaign"
    }))

    # Create empty npcs.json index
    npcs_file = test_campaign_dir / "npcs.json"
    npcs_file.write_text(json.dumps({}))

    return {
        "campaigns_dir": campaigns_dir,
        "list_file": list_file,
        "campaign_dir": test_campaign_dir,
        "campaign_id": "test-123"
    }


@pytest.fixture
def patched_repos(campaign_dir):
    """Patch utils module to use temp directories, then import repos."""
    with patch.object(utils, 'CAMPAIGNS_DIR', campaign_dir["campaigns_dir"]), \
         patch.object(utils, 'LIST_FILE', campaign_dir["list_file"]):

        # Re-import to get fresh instances with patched paths
        from repository_json import (
            JsonCampaignRepository,
            JsonNPCRepository,
            JsonBestiaryRepository,
            JsonCombatRepository,
            JsonPlayerRepository,
        )

        yield {
            "campaign": JsonCampaignRepository(),
            "npc": JsonNPCRepository(),
            "bestiary": JsonBestiaryRepository(),
            "combat": JsonCombatRepository(),
            "player": JsonPlayerRepository(),
            "campaign_id": campaign_dir["campaign_id"],
            "campaign_dir": campaign_dir["campaign_dir"],
        }


class TestJsonCampaignRepository:
    def test_get_campaign(self, patched_repos):
        repo = patched_repos["campaign"]
        campaign_id = patched_repos["campaign_id"]

        campaign = repo.get_campaign(campaign_id)
        assert campaign is not None
        assert campaign["name"] == "Test Campaign"

    def test_get_campaign_not_found(self, patched_repos):
        repo = patched_repos["campaign"]

        campaign = repo.get_campaign("nonexistent-123")
        assert campaign is None

    def test_save_campaign(self, patched_repos):
        repo = patched_repos["campaign"]
        campaign_id = patched_repos["campaign_id"]

        updated_data = {
            "name": "Updated Campaign",
            "description": "Updated description"
        }
        repo.save_campaign(campaign_id, updated_data)

        campaign = repo.get_campaign(campaign_id)
        assert campaign["name"] == "Updated Campaign"

    def test_list_campaigns(self, patched_repos):
        repo = patched_repos["campaign"]

        campaigns = repo.list_campaigns()
        assert "test-123" in campaigns
        assert campaigns["test-123"] == "test-campaign"


class TestJsonNPCRepository:
    def test_create_and_get_npc(self, patched_repos):
        repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc_data = {
            "name": "Steve",
            "keywords": ["steve", "blacksmith"],
            "arc": "A friendly blacksmith",
            "health": 20,
            "max_health": 20,
            "hit_chance": 50,
            "inventory": {"money": 0, "items": {}}
        }

        repo.create_npc(campaign_id, "steve", npc_data, ["steve", "blacksmith"])

        # Verify NPC file created
        retrieved = repo.get_npc(campaign_id, "steve")
        assert retrieved is not None
        assert retrieved["name"] == "Steve"
        assert retrieved["arc"] == "A friendly blacksmith"

        # Verify index updated
        index = repo.get_npc_index(campaign_id)
        assert "steve" in index
        assert index["steve"]["keywords"] == ["steve", "blacksmith"]

    def test_get_npc_not_found(self, patched_repos):
        repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc = repo.get_npc(campaign_id, "nonexistent")
        assert npc is None

    def test_delete_npc(self, patched_repos):
        repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        # Create NPC first
        npc_data = {"name": "Bob", "health": 10}
        repo.create_npc(campaign_id, "bob", npc_data, ["bob"])

        # Verify created
        assert repo.get_npc(campaign_id, "bob") is not None

        # Delete
        repo.delete_npc(campaign_id, "bob")

        # Verify deleted
        assert repo.get_npc(campaign_id, "bob") is None
        assert "bob" not in repo.get_npc_index(campaign_id)

    def test_save_npc_updates_existing(self, patched_repos):
        repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        # Create
        repo.create_npc(campaign_id, "alice", {"name": "Alice", "health": 20}, ["alice"])

        # Update
        repo.save_npc(campaign_id, "alice", {"name": "Alice", "health": 15})

        # Verify
        npc = repo.get_npc(campaign_id, "alice")
        assert npc["health"] == 15


class TestJsonBestiaryRepository:
    def test_get_empty_bestiary(self, patched_repos):
        repo = patched_repos["bestiary"]
        campaign_id = patched_repos["campaign_id"]

        bestiary = repo.get_bestiary(campaign_id)
        assert bestiary == {}

    def test_save_and_get_bestiary(self, patched_repos):
        repo = patched_repos["bestiary"]
        campaign_id = patched_repos["campaign_id"]

        bestiary = {
            "goblin": {
                "threat_level": "low",
                "hp": "2d6",
                "weapons": {"Rusty Dagger": "1d4"}
            }
        }

        repo.save_bestiary(campaign_id, bestiary)

        retrieved = repo.get_bestiary(campaign_id)
        assert "goblin" in retrieved
        assert retrieved["goblin"]["threat_level"] == "low"

    def test_get_entry(self, patched_repos):
        repo = patched_repos["bestiary"]
        campaign_id = patched_repos["campaign_id"]

        bestiary = {
            "dragon": {"threat_level": "deadly", "hp": "10d10", "weapons": {"Fire Breath": "4d6"}}
        }
        repo.save_bestiary(campaign_id, bestiary)

        entry = repo.get_entry(campaign_id, "Dragon")  # Test case insensitivity
        assert entry is not None
        assert entry["threat_level"] == "deadly"

        missing = repo.get_entry(campaign_id, "unicorn")
        assert missing is None


class TestJsonCombatRepository:
    def test_no_combat_initially(self, patched_repos):
        repo = patched_repos["combat"]
        campaign_id = patched_repos["campaign_id"]

        assert repo.has_combat(campaign_id) is False
        assert repo.get_combat_state(campaign_id) is None

    def test_save_and_get_combat(self, patched_repos):
        repo = patched_repos["combat"]
        campaign_id = patched_repos["campaign_id"]

        combat_state = {
            "participants": {
                "Steve": {"health": 20, "max_health": 20},
                "Goblin": {"health": 5, "max_health": 5}
            },
            "turn_order": ["Steve", "Goblin"],
            "current_turn": 0
        }

        repo.save_combat_state(campaign_id, combat_state)

        assert repo.has_combat(campaign_id) is True

        retrieved = repo.get_combat_state(campaign_id)
        assert "Steve" in retrieved["participants"]
        assert retrieved["current_turn"] == 0

    def test_delete_combat(self, patched_repos):
        repo = patched_repos["combat"]
        campaign_id = patched_repos["campaign_id"]

        repo.save_combat_state(campaign_id, {"participants": {}})
        assert repo.has_combat(campaign_id) is True

        repo.delete_combat_state(campaign_id)
        assert repo.has_combat(campaign_id) is False


class TestJsonPlayerRepository:
    def test_no_player_initially(self, patched_repos):
        repo = patched_repos["player"]
        campaign_id = patched_repos["campaign_id"]

        player = repo.get_player(campaign_id)
        assert player is None

    def test_save_and_get_player(self, patched_repos):
        repo = patched_repos["player"]
        campaign_id = patched_repos["campaign_id"]

        player_data = {
            "name": "Hero",
            "health": 30,
            "max_health": 30,
            "inventory": {"money": 100, "items": {"Sword": {"damage": "1d8"}}}
        }

        repo.save_player(campaign_id, player_data)

        retrieved = repo.get_player(campaign_id)
        assert retrieved["name"] == "Hero"
        assert retrieved["inventory"]["money"] == 100


class TestResolveNPCByKeyword:
    """Test the resolve_npc_by_keyword helper function."""

    def test_resolve_by_slug(self, patched_repos):
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        # Create NPC
        npc_data = {
            "name": "Steve the Blacksmith",
            "keywords": ["steve", "blacksmith", "smith"],
        }
        npc_repo.create_npc(campaign_id, "steve-the-blacksmith", npc_data, ["steve", "blacksmith", "smith"])

        # Patch and import
        with patch.object(utils, 'CAMPAIGNS_DIR', patched_repos["campaign_dir"].parent), \
             patch.object(utils, 'LIST_FILE', patched_repos["campaign_dir"].parent / "list.json"):

            # Need to reload repos module to use patched paths
            import importlib
            import repos as repos_module
            importlib.reload(repos_module)

            slug, data = repos_module.resolve_npc_by_keyword(campaign_id, "Steve the Blacksmith")
            assert slug == "steve-the-blacksmith"
            assert data["name"] == "Steve the Blacksmith"

    def test_resolve_by_keyword(self, patched_repos):
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc_data = {
            "name": "Marcus the Guard",
            "keywords": ["marcus", "guard", "soldier"],
        }
        npc_repo.create_npc(campaign_id, "marcus-the-guard", npc_data, ["marcus", "guard", "soldier"])

        with patch.object(utils, 'CAMPAIGNS_DIR', patched_repos["campaign_dir"].parent), \
             patch.object(utils, 'LIST_FILE', patched_repos["campaign_dir"].parent / "list.json"):

            import importlib
            import repos as repos_module
            importlib.reload(repos_module)

            # Resolve by keyword "guard"
            slug, data = repos_module.resolve_npc_by_keyword(campaign_id, "guard")
            assert slug == "marcus-the-guard"
            assert data["name"] == "Marcus the Guard"

    def test_resolve_not_found(self, patched_repos):
        with patch.object(utils, 'CAMPAIGNS_DIR', patched_repos["campaign_dir"].parent), \
             patch.object(utils, 'LIST_FILE', patched_repos["campaign_dir"].parent / "list.json"):

            import importlib
            import repos as repos_module
            importlib.reload(repos_module)

            slug, data = repos_module.resolve_npc_by_keyword(patched_repos["campaign_id"], "nobody")
            assert slug is None
            assert data is None


class TestSyncNPCToCombat:
    """Test the sync_npc_to_combat helper function."""

    def test_sync_updates_combat_health(self, patched_repos):
        npc_repo = patched_repos["npc"]
        combat_repo = patched_repos["combat"]
        campaign_id = patched_repos["campaign_id"]

        # Create NPC
        npc_repo.create_npc(campaign_id, "steve", {"name": "Steve", "health": 20}, ["steve"])

        # Start combat with Steve
        combat_state = {
            "participants": {
                "Steve": {"health": 20, "max_health": 20}
            }
        }
        combat_repo.save_combat_state(campaign_id, combat_state)

        with patch.object(utils, 'CAMPAIGNS_DIR', patched_repos["campaign_dir"].parent), \
             patch.object(utils, 'LIST_FILE', patched_repos["campaign_dir"].parent / "list.json"):

            import importlib
            import repos as repos_module
            importlib.reload(repos_module)

            # Sync new health
            repos_module.sync_npc_to_combat(campaign_id, "steve", 15)

            # Verify combat state updated
            updated = combat_repo.get_combat_state(campaign_id)
            assert updated["participants"]["Steve"]["health"] == 15

    def test_sync_no_combat_active(self, patched_repos):
        """Sync should not error when no combat is active."""
        campaign_id = patched_repos["campaign_id"]

        with patch.object(utils, 'CAMPAIGNS_DIR', patched_repos["campaign_dir"].parent), \
             patch.object(utils, 'LIST_FILE', patched_repos["campaign_dir"].parent / "list.json"):

            import importlib
            import repos as repos_module
            importlib.reload(repos_module)

            # Should not raise
            repos_module.sync_npc_to_combat(campaign_id, "steve", 10)


class TestNPCInsights:
    """Test NPC insights feature."""

    def test_npc_created_with_empty_insights(self, patched_repos):
        """New NPCs should have empty insights array."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc_data = {
            "name": "Steve",
            "insights": [],
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "steve", npc_data, ["steve"])

        retrieved = npc_repo.get_npc(campaign_id, "steve")
        assert retrieved["insights"] == []

    def test_add_insight_to_npc(self, patched_repos):
        """Test adding insights to NPC."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc_data = {
            "name": "Steve",
            "insights": [],
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "steve", npc_data, ["steve"])

        # Add an insight
        npc = npc_repo.get_npc(campaign_id, "steve")
        npc["insights"].append("Witnessed the player slay the dragon")
        npc_repo.save_npc(campaign_id, "steve", npc)

        # Verify
        retrieved = npc_repo.get_npc(campaign_id, "steve")
        assert len(retrieved["insights"]) == 1
        assert "dragon" in retrieved["insights"][0]

    def test_multiple_insights(self, patched_repos):
        """Test adding multiple insights."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc_data = {
            "name": "Marcus",
            "insights": [],
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "marcus", npc_data, ["marcus"])

        # Add multiple insights
        npc = npc_repo.get_npc(campaign_id, "marcus")
        npc["insights"].append("Learned the mayor is corrupt")
        npc["insights"].append("Discovered a secret passage")
        npc["insights"].append("Saw the player steal from the merchant")
        npc_repo.save_npc(campaign_id, "marcus", npc)

        retrieved = npc_repo.get_npc(campaign_id, "marcus")
        assert len(retrieved["insights"]) == 3

    def test_insights_purged_on_delete(self, patched_repos):
        """Insights are lost when NPC is deleted (dies)."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc_data = {
            "name": "Bob",
            "insights": ["Knew too much", "Had secrets"],
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "bob", npc_data, ["bob"])

        # Bob dies (gets deleted)
        npc_repo.delete_npc(campaign_id, "bob")

        # Insights are gone with the NPC
        assert npc_repo.get_npc(campaign_id, "bob") is None

    def test_backwards_compat_npc_without_insights(self, patched_repos):
        """Older NPCs without insights field should work."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        # Create NPC without insights field (simulating old data)
        old_npc_data = {
            "name": "Old Timer",
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "old-timer", old_npc_data, ["old"])

        # Should still work - just no insights
        retrieved = npc_repo.get_npc(campaign_id, "old-timer")
        assert retrieved is not None
        assert retrieved.get("insights") is None  # Old format has no insights


class TestNPCTodos:
    """Test NPC todo/quest system."""

    def test_npc_created_with_empty_todos(self, patched_repos):
        """New NPCs should have empty todos array."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc_data = {
            "name": "Steve",
            "insights": [],
            "todos": [],
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "steve", npc_data, ["steve"])

        retrieved = npc_repo.get_npc(campaign_id, "steve")
        assert retrieved["todos"] == []

    def test_add_todo_to_npc(self, patched_repos):
        """Test adding a todo to NPC."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc_data = {
            "name": "Steve",
            "insights": [],
            "todos": [],
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "steve", npc_data, ["steve"])

        # Add a todo
        npc = npc_repo.get_npc(campaign_id, "steve")
        npc["todos"].append({
            "name": "Find the sword",
            "description": "Retrieve the stolen family heirloom",
            "source": "Marcus",
            "source_is_npc": True
        })
        npc_repo.save_npc(campaign_id, "steve", npc)

        # Verify
        retrieved = npc_repo.get_npc(campaign_id, "steve")
        assert len(retrieved["todos"]) == 1
        assert retrieved["todos"][0]["name"] == "Find the sword"
        assert retrieved["todos"][0]["source_is_npc"] is True

    def test_complete_todo_removes_from_list(self, patched_repos):
        """Completing a todo removes it from the list."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc_data = {
            "name": "Steve",
            "insights": [],
            "todos": [{
                "name": "Find the sword",
                "description": "Get it",
                "source": "Marcus",
                "source_is_npc": True
            }],
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "steve", npc_data, ["steve"])

        # Remove the todo (simulating completion)
        npc = npc_repo.get_npc(campaign_id, "steve")
        npc["todos"].pop(0)
        npc["insights"].append("Completed 'Find the sword'")
        npc_repo.save_npc(campaign_id, "steve", npc)

        # Verify
        retrieved = npc_repo.get_npc(campaign_id, "steve")
        assert len(retrieved["todos"]) == 0
        assert len(retrieved["insights"]) == 1

    def test_todo_with_npc_source_cross_reference(self, patched_repos):
        """Test that todos track NPC sources for insight propagation."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        # Create two NPCs
        steve_data = {
            "name": "Steve",
            "insights": [],
            "todos": [{
                "name": "Deliver package",
                "description": "Bring the package to the inn",
                "source": "Marcus the Guard",
                "source_is_npc": True
            }],
            "health": 20,
        }
        marcus_data = {
            "name": "Marcus the Guard",
            "insights": [],
            "todos": [],
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "steve", steve_data, ["steve"])
        npc_repo.create_npc(campaign_id, "marcus-the-guard", marcus_data, ["marcus", "guard"])

        # Complete Steve's todo and add insight to both
        steve = npc_repo.get_npc(campaign_id, "steve")
        todo = steve["todos"].pop(0)
        steve["insights"].append(f"Completed '{todo['name']}' for {todo['source']}")
        npc_repo.save_npc(campaign_id, "steve", steve)

        # Add insight to Marcus (the source)
        marcus = npc_repo.get_npc(campaign_id, "marcus-the-guard")
        marcus["insights"].append(f"Steve completed 'Deliver package' for them")
        npc_repo.save_npc(campaign_id, "marcus-the-guard", marcus)

        # Verify both have insights
        steve_final = npc_repo.get_npc(campaign_id, "steve")
        marcus_final = npc_repo.get_npc(campaign_id, "marcus-the-guard")
        assert len(steve_final["insights"]) == 1
        assert len(marcus_final["insights"]) == 1
        assert "Deliver package" in marcus_final["insights"][0]

    def test_todo_source_npc_dead_no_insight(self, patched_repos):
        """If source NPC is dead, no insight is added to them."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        # Create Steve with a todo from Marcus
        steve_data = {
            "name": "Steve",
            "insights": [],
            "todos": [{
                "name": "Avenge Marcus",
                "description": "Kill the bandits",
                "source": "Marcus",
                "source_is_npc": True
            }],
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "steve", steve_data, ["steve"])

        # Marcus is dead (doesn't exist)
        # Complete todo - should only add insight to Steve
        steve = npc_repo.get_npc(campaign_id, "steve")
        todo = steve["todos"].pop(0)
        steve["insights"].append(f"Completed '{todo['name']}'")
        npc_repo.save_npc(campaign_id, "steve", steve)

        # Steve has insight, Marcus doesn't exist
        steve_final = npc_repo.get_npc(campaign_id, "steve")
        assert len(steve_final["insights"]) == 1
        assert npc_repo.get_npc(campaign_id, "marcus") is None

    def test_abandon_todo(self, patched_repos):
        """Abandoning a todo removes it and adds insight."""
        npc_repo = patched_repos["npc"]
        campaign_id = patched_repos["campaign_id"]

        npc_data = {
            "name": "Steve",
            "insights": [],
            "todos": [{
                "name": "Find treasure",
                "description": "Search the cave",
                "source": "self",
                "source_is_npc": False
            }],
            "health": 20,
        }
        npc_repo.create_npc(campaign_id, "steve", npc_data, ["steve"])

        # Abandon the todo
        npc = npc_repo.get_npc(campaign_id, "steve")
        todo = npc["todos"].pop(0)
        npc["insights"].append(f"Abandoned '{todo['name']}': The cave collapsed")
        npc_repo.save_npc(campaign_id, "steve", npc)

        # Verify
        retrieved = npc_repo.get_npc(campaign_id, "steve")
        assert len(retrieved["todos"]) == 0
        assert "Abandoned" in retrieved["insights"][0]
        assert "cave collapsed" in retrieved["insights"][0]
