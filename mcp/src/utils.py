import json
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
    else:
        return "critically wounded"
