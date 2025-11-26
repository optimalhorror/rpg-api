"""Tests for utils.py pure functions."""
import pytest
from unittest.mock import patch
from utils import (
    slugify,
    roll_dice,
    threat_level_to_hit_chance,
    health_description,
    damage_descriptor,
    healing_descriptor,
    format_list_from_dict,
    err_not_found,
    err_already_exists,
    err_missing,
    err_required,
    err_invalid,
)


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slugify("Steve's Campaign!") == "steves-campaign"

    def test_multiple_spaces(self):
        assert slugify("The   Big   Quest") == "the-big-quest"

    def test_leading_trailing(self):
        assert slugify("  trimmed  ") == "trimmed"

    def test_underscores(self):
        assert slugify("snake_case_name") == "snake-case-name"

    def test_mixed(self):
        assert slugify("--My--Cool--Campaign--") == "my-cool-campaign"


class TestRollDice:
    """Test dice rolling with mocked randomness for deterministic results."""

    def test_plain_number(self):
        assert roll_dice("20") == 20
        assert roll_dice("0") == 0
        assert roll_dice("100") == 100

    def test_simple_dice_max(self):
        """Mock random to always return max."""
        with patch("utils.random.randint", return_value=6):
            assert roll_dice("1d6") == 6
            assert roll_dice("2d6") == 12
            assert roll_dice("d6") == 6  # implicit 1d6

    def test_simple_dice_min(self):
        """Mock random to always return 1."""
        with patch("utils.random.randint", return_value=1):
            assert roll_dice("1d6") == 1
            assert roll_dice("2d6") == 2
            assert roll_dice("3d8") == 3

    def test_dice_with_positive_modifier(self):
        with patch("utils.random.randint", return_value=3):
            assert roll_dice("1d6+2") == 5
            assert roll_dice("2d4+10") == 16

    def test_dice_with_negative_modifier(self):
        with patch("utils.random.randint", return_value=4):
            assert roll_dice("1d6-1") == 3
            assert roll_dice("2d6-2") == 6

    def test_modifier_first_addition(self):
        """Test 10+1d6 format."""
        with patch("utils.random.randint", return_value=5):
            assert roll_dice("10+1d6") == 15
            assert roll_dice("80+5d10") == 105

    def test_modifier_first_subtraction(self):
        """Test 20-1d6 format."""
        with patch("utils.random.randint", return_value=3):
            assert roll_dice("20-1d6") == 17
            assert roll_dice("100-2d10") == 94

    def test_case_insensitive(self):
        with patch("utils.random.randint", return_value=4):
            assert roll_dice("1D6") == 4
            assert roll_dice("2D8+5") == 13

    def test_whitespace_handling(self):
        with patch("utils.random.randint", return_value=3):
            assert roll_dice("  1d6  ") == 3
            assert roll_dice(" 2d4+1 ") == 7

    def test_edge_case_1d1(self):
        """1d1 always returns 1."""
        assert roll_dice("1d1") == 1

    def test_edge_case_0d6(self):
        """0d6 should return 0 (no dice rolled)."""
        assert roll_dice("0d6") == 0

    # Invalid inputs - fallback to 1
    def test_invalid_banana(self):
        """Invalid dice formula falls back to 1."""
        assert roll_dice("banana") == 1

    def test_invalid_potato(self):
        assert roll_dice("potato") == 1

    def test_invalid_empty(self):
        assert roll_dice("") == 1

    def test_invalid_garbage(self):
        assert roll_dice("abc123xyz") == 1

    def test_invalid_partial(self):
        """Partial dice notation that doesn't match pattern."""
        assert roll_dice("d") == 1
        assert roll_dice("1d") == 1
        assert roll_dice("dx") == 1


class TestThreatLevelToHitChance:
    def test_all_levels(self):
        assert threat_level_to_hit_chance("none") == 10
        assert threat_level_to_hit_chance("negligible") == 25
        assert threat_level_to_hit_chance("low") == 35
        assert threat_level_to_hit_chance("moderate") == 50
        assert threat_level_to_hit_chance("high") == 65
        assert threat_level_to_hit_chance("deadly") == 80
        assert threat_level_to_hit_chance("certain_death") == 95

    def test_unknown_defaults_to_50(self):
        assert threat_level_to_hit_chance("unknown") == 50
        assert threat_level_to_hit_chance("banana") == 50
        assert threat_level_to_hit_chance("") == 50


class TestHealthDescription:
    def test_dead(self):
        assert health_description(0, 20) == "dead"
        assert health_description(-5, 20) == "dead"

    def test_perfect_health(self):
        assert health_description(20, 20) == "in perfect health"
        assert health_description(25, 20) == "in perfect health"  # overheal

    def test_slightly_wounded(self):
        assert health_description(16, 20) == "slightly wounded"  # 80%
        assert health_description(15, 20) == "slightly wounded"  # 75%

    def test_moderately_wounded(self):
        assert health_description(14, 20) == "moderately wounded"  # 70%
        assert health_description(10, 20) == "moderately wounded"  # 50%

    def test_severely_wounded(self):
        assert health_description(9, 20) == "severely wounded"  # 45%
        assert health_description(5, 20) == "severely wounded"  # 25%

    def test_badly_wounded(self):
        assert health_description(4, 20) == "badly wounded"  # 20%
        assert health_description(2, 20) == "badly wounded"  # 10%

    def test_critically_wounded(self):
        assert health_description(1, 20) == "critically wounded"  # 5%


class TestDamageDescriptor:
    def test_barely_grazes(self):
        assert damage_descriptor(1, "1d6") == "barely grazes"
        # 2/6 = 33.33% is exactly on boundary, goes to next tier

    def test_strikes_lightly(self):
        assert damage_descriptor(3, "1d6") == "strikes lightly"

    def test_lands(self):
        assert damage_descriptor(4, "1d6") == "lands"

    def test_strikes_solidly(self):
        assert damage_descriptor(5, "1d6") == "strikes solidly"

    def test_devastating(self):
        assert damage_descriptor(6, "1d6") == "crashes down with devastating force"
        assert damage_descriptor(12, "2d6") == "crashes down with devastating force"

    def test_with_modifier(self):
        # 2d6+2 has max damage of 14
        assert damage_descriptor(14, "2d6+2") == "crashes down with devastating force"
        assert damage_descriptor(2, "2d6+2") == "barely grazes"

    def test_plain_number_formula(self):
        assert damage_descriptor(10, "10") == "crashes down with devastating force"
        assert damage_descriptor(3, "10") == "barely grazes"

    def test_invalid_formula_fallback(self):
        # Invalid formula defaults to max_damage=6
        assert damage_descriptor(6, "banana") == "crashes down with devastating force"
        assert damage_descriptor(1, "potato") == "barely grazes"


class TestHealingDescriptor:
    def test_minor_recovery(self):
        assert healing_descriptor(1, "1d6") == "minor recovery"

    def test_light_healing(self):
        assert healing_descriptor(3, "1d6") == "light healing"

    def test_moderate_recovery(self):
        assert healing_descriptor(4, "1d6") == "moderate recovery"

    def test_strong_healing(self):
        assert healing_descriptor(5, "1d6") == "strong healing"

    def test_major_restoration(self):
        assert healing_descriptor(6, "1d6") == "major restoration"
        assert healing_descriptor(12, "2d6") == "major restoration"


class TestFormatListFromDict:
    def test_basic(self):
        assert format_list_from_dict({"a": 1, "b": 2}) == "a, b"

    def test_empty(self):
        assert format_list_from_dict({}) == "none"

    def test_none(self):
        assert format_list_from_dict(None) == "none"

    def test_custom_empty_message(self):
        assert format_list_from_dict({}, "no items") == "no items"
        assert format_list_from_dict(None, "nothing") == "nothing"


class TestErrorFormatting:
    def test_err_not_found_basic(self):
        assert err_not_found("NPC", "Steve") == "NPC 'Steve' not found."

    def test_err_not_found_with_hint(self):
        result = err_not_found("NPC", "Steve", "Use list_npcs to see available NPCs.")
        assert result == "NPC 'Steve' not found. Use list_npcs to see available NPCs."

    def test_err_already_exists_basic(self):
        assert err_already_exists("Item", "Sword") == "Item 'Sword' already exists."

    def test_err_already_exists_with_hint(self):
        result = err_already_exists("Item", "Sword", "Use get_inventory to view.")
        assert result == "Item 'Sword' already exists. Use get_inventory to view."

    def test_err_missing_basic(self):
        assert err_missing("Steve", "Sword") == "Steve doesn't have 'Sword'."

    def test_err_missing_with_available(self):
        result = err_missing("Steve", "Sword", "Dagger, Axe")
        assert result == "Steve doesn't have 'Sword'. Available: Dagger, Axe"

    def test_err_required(self):
        assert err_required("campaign_id") == "campaign_id is required."

    def test_err_invalid_basic(self):
        assert err_invalid("Damage must be specified.") == "Damage must be specified."

    def test_err_invalid_with_hint(self):
        result = err_invalid("Invalid dice format.", "Use XdY notation.")
        assert result == "Invalid dice format. Use XdY notation."
