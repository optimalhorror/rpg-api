from mcp.types import Tool, TextContent
from utils import roll_dice, slugify, format_list_from_dict
from repos import npc_repo


def ensure_inventory(npc_data: dict) -> None:
    """Ensure NPC has inventory initialized with default structure."""
    if "inventory" not in npc_data:
        npc_data["inventory"] = {"money": 0, "items": {}}


def get_add_item_tool() -> Tool:
    return Tool(
        name="add_item",
        description="Add an item to an NPC's inventory. Items can be weapons, consumables, or containers.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign UUID",
                },
                "npc_name": {
                    "type": "string",
                    "description": "Name of the NPC to give the item to",
                },
                "item_name": {
                    "type": "string",
                    "description": "Name of the item (used as key)",
                },
                "description": {
                    "type": "string",
                    "description": "Description of the item",
                },
                "source": {
                    "type": "string",
                    "description": "Where the item came from (e.g., 'looted from goblin', 'bought at market')",
                },
                "weapon": {
                    "type": "boolean",
                    "description": "Whether this item can be used as a weapon in combat",
                    "default": False,
                },
                "damage": {
                    "type": "string",
                    "description": "Damage dice for weapon (e.g., '1d8', '2d6'). Required if weapon=true.",
                },
                "container": {
                    "type": "string",
                    "description": "Optional: Name of container item this is stored in (e.g., 'backpack')",
                },
            },
            "required": ["campaign_id", "npc_name", "item_name", "description", "source"],
        }
    )


async def handle_add_item(arguments: dict) -> list[TextContent]:
    campaign_id = arguments["campaign_id"]
    npc_name = arguments["npc_name"]
    item_name = arguments["item_name"]
    description = arguments["description"]
    source = arguments["source"]
    weapon = arguments.get("weapon", False)
    damage = arguments.get("damage")
    container = arguments.get("container")

    # Slugify NPC name
    npc_slug = slugify(npc_name)

    # Load NPC
    npc_data = npc_repo.get_npc(campaign_id, npc_slug)
    if not npc_data:
        return [TextContent(
            type="text",
            text=f"Error: NPC '{npc_name}' not found in campaign {campaign_id}"
        )]

    # Validate weapon requirements
    if weapon and not damage:
        return [TextContent(
            type="text",
            text="Error: Weapon items must have damage specified"
        )]

    # Initialize inventory if needed
    ensure_inventory(npc_data)

    # Check if item already exists
    if item_name in npc_data["inventory"]["items"]:
        return [TextContent(
            type="text",
            text=f"Error: {npc_name} already has an item named '{item_name}'"
        )]

    # Validate container exists if specified
    if container:
        items = npc_data["inventory"]["items"]
        if container not in items:
            items_list = format_list_from_dict(items)
            return [TextContent(
                type="text",
                text=f"Error: Container '{container}' not found in {npc_name}'s inventory. Available items: {items_list}"
            )]

    # Create item
    item_data = {
        "description": description,
        "source": source,
        "weapon": weapon,
    }
    if damage:
        item_data["damage"] = damage
    if container:
        item_data["container"] = container

    # Add to inventory
    npc_data["inventory"]["items"][item_name] = item_data

    # Save NPC
    npc_repo.save_npc(campaign_id, npc_slug, npc_data)

    weapon_str = f" (weapon, {damage} damage)" if weapon else ""
    container_str = f" in {container}" if container else ""

    return [TextContent(
        type="text",
        text=f"Added '{item_name}'{weapon_str} to {npc_name}'s inventory{container_str}.\nSource: {source}"
    )]


def get_remove_item_tool() -> Tool:
    return Tool(
        name="remove_item",
        description="Remove an item from an NPC's inventory (discard, destroy, or consume).",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign UUID",
                },
                "npc_name": {
                    "type": "string",
                    "description": "Name of the NPC",
                },
                "item_name": {
                    "type": "string",
                    "description": "Name of the item to remove",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional: Why the item is being removed (e.g., 'ate the bread', 'threw away', 'destroyed in combat')",
                },
            },
            "required": ["campaign_id", "npc_name", "item_name"],
        }
    )


async def handle_remove_item(arguments: dict) -> list[TextContent]:
    campaign_id = arguments["campaign_id"]
    npc_name = arguments["npc_name"]
    item_name = arguments["item_name"]
    reason = arguments.get("reason", "removed")

    npc_slug = slugify(npc_name)

    npc_data = npc_repo.get_npc(campaign_id, npc_slug)
    if not npc_data:
        return [TextContent(
            type="text",
            text=f"Error: NPC '{npc_name}' not found"
        )]

    if "inventory" not in npc_data or item_name not in npc_data["inventory"]["items"]:
        return [TextContent(
            type="text",
            text=f"Error: {npc_name} doesn't have an item named '{item_name}'"
        )]

    # Remove item
    del npc_data["inventory"]["items"][item_name]

    # Clean up orphaned container references - remove container field from items that referenced this item
    items_updated = []
    for name, item in npc_data["inventory"]["items"].items():
        if item.get("container") == item_name:
            del item["container"]
            items_updated.append(name)

    npc_repo.save_npc(campaign_id, npc_slug, npc_data)

    result_text = f"Removed '{item_name}' from {npc_name}'s inventory. Reason: {reason}"
    if items_updated:
        result_text += f"\nAlso removed container reference from: {', '.join(items_updated)}"

    return [TextContent(
        type="text",
        text=result_text
    )]


def get_update_item_tool() -> Tool:
    return Tool(
        name="update_item",
        description="Update properties of an item in an NPC's inventory.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign UUID",
                },
                "npc_name": {
                    "type": "string",
                    "description": "Name of the NPC",
                },
                "item_name": {
                    "type": "string",
                    "description": "Name of the item to update",
                },
                "description": {
                    "type": "string",
                    "description": "Optional: New description",
                },
                "weapon": {
                    "type": "boolean",
                    "description": "Optional: Update weapon status",
                },
                "damage": {
                    "type": "string",
                    "description": "Optional: New damage dice",
                },
                "container": {
                    "type": "string",
                    "description": "Optional: New container location",
                },
            },
            "required": ["campaign_id", "npc_name", "item_name"],
        }
    )


async def handle_update_item(arguments: dict) -> list[TextContent]:
    campaign_id = arguments["campaign_id"]
    npc_name = arguments["npc_name"]
    item_name = arguments["item_name"]

    npc_slug = slugify(npc_name)

    npc_data = npc_repo.get_npc(campaign_id, npc_slug)
    if not npc_data:
        return [TextContent(
            type="text",
            text=f"Error: NPC '{npc_name}' not found"
        )]

    if "inventory" not in npc_data or item_name not in npc_data["inventory"]["items"]:
        return [TextContent(
            type="text",
            text=f"Error: {npc_name} doesn't have an item named '{item_name}'"
        )]

    item = npc_data["inventory"]["items"][item_name]
    updates = []

    # Update fields if provided
    if "description" in arguments:
        item["description"] = arguments["description"]
        updates.append("description")

    if "weapon" in arguments:
        item["weapon"] = arguments["weapon"]
        updates.append("weapon status")

    if "damage" in arguments:
        item["damage"] = arguments["damage"]
        updates.append("damage")

    if "container" in arguments:
        item["container"] = arguments["container"]
        updates.append("container")

    if not updates:
        return [TextContent(
            type="text",
            text=f"No updates provided for '{item_name}'"
        )]

    npc_repo.save_npc(campaign_id, npc_slug, npc_data)

    return [TextContent(
        type="text",
        text=f"Updated '{item_name}' for {npc_name}: {', '.join(updates)}"
    )]


def get_get_inventory_tool() -> Tool:
    return Tool(
        name="get_inventory",
        description="View an NPC's complete inventory including money and all items.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign UUID",
                },
                "npc_name": {
                    "type": "string",
                    "description": "Name of the NPC",
                },
            },
            "required": ["campaign_id", "npc_name"],
        }
    )


async def handle_get_inventory(arguments: dict) -> list[TextContent]:
    campaign_id = arguments["campaign_id"]
    npc_name = arguments["npc_name"]

    npc_slug = slugify(npc_name)

    npc_data = npc_repo.get_npc(campaign_id, npc_slug)
    if not npc_data:
        return [TextContent(
            type="text",
            text=f"Error: NPC '{npc_name}' not found"
        )]

    if "inventory" not in npc_data:
        return [TextContent(
            type="text",
            text=f"{npc_name} has no inventory initialized."
        )]

    inventory = npc_data["inventory"]
    result = f"=== {npc_name}'s Inventory ===\n\n"
    result += f"Money: {inventory.get('money', 0)} gold\n\n"

    items = inventory.get("items", {})
    if not items:
        result += "No items."
    else:
        result += f"Items ({len(items)}):\n"
        for name, item in items.items():
            result += f"\n• {name}\n"
            result += f"  Description: {item['description']}\n"
            result += f"  Source: {item['source']}\n"
            if item.get("weapon"):
                result += f"  Weapon: Yes (damage: {item.get('damage', 'unknown')})\n"
            if item.get("container"):
                result += f"  Container: {item['container']}\n"

    return [TextContent(
        type="text",
        text=result
    )]


def get_add_money_tool() -> Tool:
    return Tool(
        name="add_money",
        description="Add money to an NPC's inventory.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign UUID",
                },
                "npc_name": {
                    "type": "string",
                    "description": "Name of the NPC",
                },
                "amount": {
                    "type": "integer",
                    "description": "Amount of money to add (in gold)",
                },
                "source": {
                    "type": "string",
                    "description": "Optional: Where the money came from (e.g., 'looted from chest', 'quest reward')",
                },
            },
            "required": ["campaign_id", "npc_name", "amount"],
        }
    )


async def handle_add_money(arguments: dict) -> list[TextContent]:
    campaign_id = arguments["campaign_id"]
    npc_name = arguments["npc_name"]
    amount = arguments["amount"]
    source = arguments.get("source", "")

    npc_slug = slugify(npc_name)

    npc_data = npc_repo.get_npc(campaign_id, npc_slug)
    if not npc_data:
        return [TextContent(
            type="text",
            text=f"Error: NPC '{npc_name}' not found"
        )]

    # Initialize inventory if needed
    ensure_inventory(npc_data)

    old_money = npc_data["inventory"]["money"]
    npc_data["inventory"]["money"] = old_money + amount

    npc_repo.save_npc(campaign_id, npc_slug, npc_data)

    source_str = f" ({source})" if source else ""
    return [TextContent(
        type="text",
        text=f"Added {amount} gold to {npc_name}'s inventory{source_str}.\nNew balance: {npc_data['inventory']['money']} gold"
    )]


def get_remove_money_tool() -> Tool:
    return Tool(
        name="remove_money",
        description="Remove money from an NPC's inventory. Fails if NPC doesn't have enough money.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign UUID",
                },
                "npc_name": {
                    "type": "string",
                    "description": "Name of the NPC",
                },
                "amount": {
                    "type": "integer",
                    "description": "Amount of money to remove (in gold)",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional: Why money is being removed (e.g., 'bought sword', 'paid for room')",
                },
            },
            "required": ["campaign_id", "npc_name", "amount"],
        }
    )


async def handle_remove_money(arguments: dict) -> list[TextContent]:
    campaign_id = arguments["campaign_id"]
    npc_name = arguments["npc_name"]
    amount = arguments["amount"]
    reason = arguments.get("reason", "")

    npc_slug = slugify(npc_name)

    npc_data = npc_repo.get_npc(campaign_id, npc_slug)
    if not npc_data:
        return [TextContent(
            type="text",
            text=f"Error: NPC '{npc_name}' not found"
        )]

    # Initialize inventory if needed
    ensure_inventory(npc_data)

    old_money = npc_data["inventory"]["money"]

    # Check if they have enough money
    if old_money < amount:
        return [TextContent(
            type="text",
            text=f"{npc_name} only has {old_money} gold but needs {amount} gold. Not enough money to complete transaction."
        )]

    npc_data["inventory"]["money"] = old_money - amount

    npc_repo.save_npc(campaign_id, npc_slug, npc_data)

    reason_str = f" ({reason})" if reason else ""

    return [TextContent(
        type="text",
        text=f"Removed {amount} gold from {npc_name}'s inventory{reason_str}.\nNew balance: {npc_data['inventory']['money']} gold"
    )]
