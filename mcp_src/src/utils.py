import json
import random
import re
from pathlib import Path


# Project root (where campaigns/ will live)
PROJECT_ROOT = Path(__file__).parent.parent
CAMPAIGNS_DIR = PROJECT_ROOT / "campaigns"
LIST_FILE = CAMPAIGNS_DIR / "list.json"


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


def load_campaign_list() -> dict:
    """Load the campaign list mapping (id -> slug)."""
    if LIST_FILE.exists():
        return json.loads(LIST_FILE.read_text())
    return {}


def save_campaign_list(campaign_list: dict) -> None:
    """Save the campaign list mapping."""
    CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)
    LIST_FILE.write_text(json.dumps(campaign_list, indent=2))


def get_campaign_dir(campaign_id: str) -> Path:
    """Get campaign directory from ID."""
    campaign_list = load_campaign_list()
    campaign_slug = campaign_list.get(campaign_id)
    if not campaign_slug:
        raise ValueError(f"Campaign not found: {campaign_id}")
    return CAMPAIGNS_DIR / campaign_slug


def roll_dice(formula: str) -> int:
    """Roll dice from a formula like '1d6', '2d4+5', '80+5d10', '20'."""
    formula = formula.lower().strip()

    # Just a number
    if formula.isdigit():
        return int(formula)

    # Try to parse XdY+Z or XdY-Z or XdY (dice first, modifier second)
    match = re.match(r'(\d+)?d(\d+)([+-]\d+)?$', formula)
    if match:
        count = int(match.group(1) or 1)
        sides = int(match.group(2))
        modifier = int(match.group(3) or 0)

        total = sum(random.randint(1, sides) for _ in range(count))
        return total + modifier

    # Try to parse Z+XdY or Z-XdY (modifier first, dice second)
    match = re.match(r'(\d+)([+-])(\d+)?d(\d+)$', formula)
    if match:
        base = int(match.group(1))
        operator = match.group(2)
        count = int(match.group(3) or 1)
        sides = int(match.group(4))

        dice_total = sum(random.randint(1, sides) for _ in range(count))
        if operator == '+':
            return base + dice_total
        else:  # operator == '-'
            return base - dice_total

    # Fallback: just return 1
    return 1


def threat_level_to_hit_chance(threat_level: str) -> int:
    """Convert threat level to hit chance percentage."""
    threat_map = {
        "none": 10,           # fly, butterfly - mostly harmless
        "negligible": 25,     # dog, cat - can bite but not dangerous
        "low": 35,            # wolf, goblin - minor threat
        "moderate": 50,       # bandit, orc - standard threat
        "high": 65,           # mercenary, troll - serious threat
        "deadly": 80,         # dragon, demon - very dangerous
        "certain_death": 95   # eldritch horror - reality-bending
    }
    return threat_map.get(threat_level, 50)  # Default to 50% if unknown


def health_description(health: int, max_health: int) -> str:
    """Convert health to human-readable description."""
    ratio = health / max_health
    if ratio >= 1.0:
        return "in perfect health"
    elif ratio >= 0.75:
        return "slightly wounded"
    elif ratio >= 0.5:
        return "moderately wounded"
    elif ratio >= 0.25:
        return "severely wounded"
    elif ratio >= 0.1:
        return "badly wounded"
    else:
        return "critically wounded"


def damage_descriptor(damage: int, weapon_formula: str) -> str:
    """
    Convert damage amount to narrative descriptor based on weapon's potential.

    Examples:
        1d6 weapon: 1-2 = barely, 3-4 = light, 5-6 = regular, 7-8 = solid, 9+ = massive
        2d6 weapon: 2-4 = barely, 5-7 = light, 8-9 = regular, 10-11 = solid, 12+ = massive
    """
    # Parse weapon to get max potential damage
    weapon_formula = weapon_formula.lower().strip()

    # Try to extract max damage from formula
    if 'd' in weapon_formula:
        match = re.match(r'(\d+)?d(\d+)([+-]\d+)?', weapon_formula)
        if match:
            count = int(match.group(1) or 1)
            sides = int(match.group(2))
            modifier = int(match.group(3) or 0)
            max_damage = (count * sides) + modifier
        else:
            max_damage = 6  # Default fallback
    elif weapon_formula.isdigit():
        max_damage = int(weapon_formula)
    else:
        max_damage = 6  # Default fallback

    # Calculate damage as percentage of max
    ratio = damage / max_damage if max_damage > 0 else 0

    if ratio <= 0.33:
        return "barely grazes"
    elif ratio <= 0.55:
        return "strikes lightly"
    elif ratio <= 0.75:
        return "lands"
    elif ratio <= 0.95:
        return "strikes solidly"
    else:
        return "crashes down with devastating force"


def healing_descriptor(heal_amount: int, heal_formula: str) -> str:
    """
    Convert healing amount to narrative descriptor based on healing's potential.

    Examples:
        1d4 healing: 1 = minor, 2 = light, 3 = moderate, 4+ = strong
        2d6 healing: 2-4 = minor, 5-7 = light, 8-9 = moderate, 10-11 = strong, 12+ = major
    """
    # Parse healing formula to get max potential healing
    heal_formula = heal_formula.lower().strip()

    # Try to extract max healing from formula
    if 'd' in heal_formula:
        match = re.match(r'(\d+)?d(\d+)([+-]\d+)?', heal_formula)
        if match:
            count = int(match.group(1) or 1)
            sides = int(match.group(2))
            modifier = int(match.group(3) or 0)
            max_healing = (count * sides) + modifier
        else:
            max_healing = 6  # Default fallback
    elif heal_formula.isdigit():
        max_healing = int(heal_formula)
    else:
        max_healing = 6  # Default fallback

    # Calculate healing as percentage of max
    ratio = heal_amount / max_healing if max_healing > 0 else 0

    if ratio <= 0.33:
        return "minor recovery"
    elif ratio <= 0.55:
        return "light healing"
    elif ratio <= 0.75:
        return "moderate recovery"
    elif ratio <= 0.95:
        return "strong healing"
    else:
        return "major restoration"
