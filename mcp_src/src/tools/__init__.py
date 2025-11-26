from .campaign import get_begin_campaign_tool, handle_begin_campaign, get_delete_campaign_tool, handle_delete_campaign
from .npc import get_create_npc_tool, handle_create_npc, get_heal_npc_tool, handle_heal_npc
from .combat import get_attack_tool, handle_attack, get_remove_from_combat_tool, handle_remove_from_combat, get_spawn_enemy_tool, handle_spawn_enemy
from .bestiary import get_create_bestiary_entry_tool, handle_create_bestiary_entry
from .inventory import (
    get_add_item_tool, handle_add_item,
    get_remove_item_tool, handle_remove_item,
    get_update_item_tool, handle_update_item,
    get_get_inventory_tool, handle_get_inventory,
    get_add_money_tool, handle_add_money,
    get_remove_money_tool, handle_remove_money,
)
from .readers import (
    get_list_campaigns_tool, handle_list_campaigns,
    get_get_campaign_tool, handle_get_campaign,
    get_list_npcs_tool, handle_list_npcs,
    get_get_npc_tool, handle_get_npc,
    get_get_combat_status_tool, handle_get_combat_status,
    get_get_bestiary_tool, handle_get_bestiary,
)

# Single source of truth for all tools: (name, get_tool_fn, handler_fn)
# Add new tools here - server.py and mcp_bridge.py will auto-discover them
TOOL_REGISTRY = [
    # Campaign
    ("begin_campaign", get_begin_campaign_tool, handle_begin_campaign),
    ("delete_campaign", get_delete_campaign_tool, handle_delete_campaign),
    # NPC
    ("create_npc", get_create_npc_tool, handle_create_npc),
    ("heal_npc", get_heal_npc_tool, handle_heal_npc),
    # Combat
    ("attack", get_attack_tool, handle_attack),
    ("remove_from_combat", get_remove_from_combat_tool, handle_remove_from_combat),
    ("spawn_enemy", get_spawn_enemy_tool, handle_spawn_enemy),
    # Bestiary
    ("create_bestiary_entry", get_create_bestiary_entry_tool, handle_create_bestiary_entry),
    # Inventory
    ("add_item", get_add_item_tool, handle_add_item),
    ("remove_item", get_remove_item_tool, handle_remove_item),
    ("update_item", get_update_item_tool, handle_update_item),
    ("get_inventory", get_get_inventory_tool, handle_get_inventory),
    ("add_money", get_add_money_tool, handle_add_money),
    ("remove_money", get_remove_money_tool, handle_remove_money),
    # Readers
    ("list_campaigns", get_list_campaigns_tool, handle_list_campaigns),
    ("get_campaign", get_get_campaign_tool, handle_get_campaign),
    ("list_npcs", get_list_npcs_tool, handle_list_npcs),
    ("get_npc", get_get_npc_tool, handle_get_npc),
    ("get_combat_status", get_get_combat_status_tool, handle_get_combat_status),
    ("get_bestiary", get_get_bestiary_tool, handle_get_bestiary),
]


def get_all_tools():
    """Get all tool definitions."""
    return [get_tool() for _, get_tool, _ in TOOL_REGISTRY]


def get_tool_handlers():
    """Get mapping of tool names to handlers."""
    return {name: handler for name, _, handler in TOOL_REGISTRY}


async def call_tool(name: str, arguments: dict):
    """Call a tool by name."""
    handlers = get_tool_handlers()
    if name not in handlers:
        raise ValueError(f"Unknown tool: {name}")
    return await handlers[name](arguments)
