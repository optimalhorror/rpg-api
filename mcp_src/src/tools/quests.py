"""Quest/todo management tools for NPCs."""
from mcp.types import Tool, TextContent

from utils import err_not_found
from repos import npc_repo, resolve_npc_by_keyword, add_npc_insight


def _find_todo_by_name(todos: list, search_name: str) -> tuple[int, dict] | tuple[None, None]:
    """Find a todo by fuzzy name matching (case-insensitive, partial match).

    Returns (index, todo) if found, (None, None) otherwise.
    """
    search_lower = search_name.lower()

    # First try exact match
    for i, todo in enumerate(todos):
        if todo["name"].lower() == search_lower:
            return i, todo

    # Then try partial match (search term in todo name)
    for i, todo in enumerate(todos):
        if search_lower in todo["name"].lower():
            return i, todo

    # Finally try partial match (todo name in search term)
    for i, todo in enumerate(todos):
        if todo["name"].lower() in search_lower:
            return i, todo

    return None, None


def get_add_npc_todo_tool() -> Tool:
    """Return the add_npc_todo tool definition."""
    return Tool(
        name="add_npc_todo",
        description="Add a task/quest to an NPC's todo list. Tasks can be assigned by other NPCs, objects, self-imposed, etc. When completed or abandoned, insights are automatically added to both the NPC and source (if source is an NPC).",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID"
                },
                "npc_name": {
                    "type": "string",
                    "description": "Name or keyword of the NPC receiving the task"
                },
                "todo_name": {
                    "type": "string",
                    "description": "Short name/title of the task (e.g., 'Retrieve the stolen sword')"
                },
                "description": {
                    "type": "string",
                    "description": "Details about what needs to be done"
                },
                "source": {
                    "type": "string",
                    "description": "Who/what assigned the task (NPC name/keyword, object name, 'self', etc.)"
                },
                "source_is_npc": {
                    "type": "boolean",
                    "description": "True if source is an NPC (for insight propagation on completion/abandonment)"
                }
            },
            "required": ["campaign_id", "npc_name", "todo_name", "description", "source", "source_is_npc"]
        }
    )


async def handle_add_npc_todo(arguments: dict) -> list[TextContent]:
    """Handle the add_npc_todo tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        npc_name = arguments["npc_name"]
        todo_name = arguments["todo_name"]
        description = arguments["description"]
        source = arguments["source"]
        source_is_npc = arguments["source_is_npc"]

        # Resolve target NPC
        npc_slug, npc_data = resolve_npc_by_keyword(campaign_id, npc_name)
        if not npc_data:
            return [TextContent(
                type="text",
                text=err_not_found("NPC", npc_name, "Use NPC name or keyword.")
            )]

        # If source is NPC, resolve to get their actual name
        source_name = source
        if source_is_npc:
            _, source_npc = resolve_npc_by_keyword(campaign_id, source)
            if source_npc:
                source_name = source_npc.get("name", source)

        # Initialize todos if not present (backwards compat)
        if "todos" not in npc_data:
            npc_data["todos"] = []

        # Create todo
        todo = {
            "name": todo_name,
            "description": description,
            "source": source_name,
            "source_is_npc": source_is_npc
        }

        npc_data["todos"].append(todo)
        npc_repo.save_npc(campaign_id, npc_slug, npc_data)

        resolved_name = npc_data.get("name", npc_name)
        todo_count = len(npc_data["todos"])

        return [TextContent(
            type="text",
            text=f"Todo '{todo_name}' added to {resolved_name}.\nSource: {source_name}\nTotal todos: {todo_count}"
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Error adding todo: {str(e)}")]


def get_complete_todo_tool() -> Tool:
    """Return the complete_todo tool definition."""
    return Tool(
        name="complete_todo",
        description="Mark an NPC's task as complete. Adds insight to the NPC about completing the task. If the source was an NPC (and still alive), adds insight to them about who completed it for them.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID"
                },
                "npc_name": {
                    "type": "string",
                    "description": "Name or keyword of the NPC who completed the task"
                },
                "todo_name": {
                    "type": "string",
                    "description": "Name of the todo to complete (fuzzy match supported)"
                },
                "resolution": {
                    "type": "string",
                    "description": "How the task was resolved (e.g., 'Retrieved the sword by defeating the bandits')"
                }
            },
            "required": ["campaign_id", "npc_name", "todo_name", "resolution"]
        }
    )


async def handle_complete_todo(arguments: dict) -> list[TextContent]:
    """Handle the complete_todo tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        npc_name = arguments["npc_name"]
        todo_name = arguments["todo_name"]
        resolution = arguments["resolution"]

        # Resolve NPC
        npc_slug, npc_data = resolve_npc_by_keyword(campaign_id, npc_name)
        if not npc_data:
            return [TextContent(
                type="text",
                text=err_not_found("NPC", npc_name, "Use NPC name or keyword.")
            )]

        resolved_name = npc_data.get("name", npc_name)

        # Initialize if needed (backwards compat)
        if "todos" not in npc_data:
            npc_data["todos"] = []
        if "insights" not in npc_data:
            npc_data["insights"] = []

        # Find the todo
        todo_idx, todo = _find_todo_by_name(npc_data["todos"], todo_name)
        if todo is None:
            available = ", ".join([t["name"] for t in npc_data["todos"]]) or "none"
            return [TextContent(
                type="text",
                text=f"Todo '{todo_name}' not found for {resolved_name}. Available: {available}"
            )]

        # Remove todo from list
        npc_data["todos"].pop(todo_idx)

        # Add insight to NPC
        npc_insight = f"Completed '{todo['name']}' for {todo['source']}: {resolution}"
        npc_data["insights"].append(npc_insight)

        npc_repo.save_npc(campaign_id, npc_slug, npc_data)

        result_lines = [
            f"{resolved_name} completed '{todo['name']}'.",
            f"Resolution: {resolution}",
            f"Insight added to {resolved_name}."
        ]

        # If source was NPC, add insight to them
        if todo["source_is_npc"]:
            source_insight = f"{resolved_name} completed '{todo['name']}' for them: {resolution}"
            if add_npc_insight(campaign_id, todo["source"], source_insight):
                result_lines.append(f"Insight added to {todo['source']}.")
            else:
                result_lines.append(f"({todo['source']} no longer exists - no insight added)")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error completing todo: {str(e)}")]


def get_abandon_todo_tool() -> Tool:
    """Return the abandon_todo tool definition."""
    return Tool(
        name="abandon_todo",
        description="Mark an NPC's task as abandoned. Adds insight to the NPC about abandoning it. If the source was an NPC (and still alive), adds insight to them that the task was never completed.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID"
                },
                "npc_name": {
                    "type": "string",
                    "description": "Name or keyword of the NPC abandoning the task"
                },
                "todo_name": {
                    "type": "string",
                    "description": "Name of the todo to abandon (fuzzy match supported)"
                },
                "reason": {
                    "type": "string",
                    "description": "Why the task was abandoned (e.g., 'The bandits fled the region')"
                }
            },
            "required": ["campaign_id", "npc_name", "todo_name", "reason"]
        }
    )


async def handle_abandon_todo(arguments: dict) -> list[TextContent]:
    """Handle the abandon_todo tool call."""
    try:
        campaign_id = arguments["campaign_id"]
        npc_name = arguments["npc_name"]
        todo_name = arguments["todo_name"]
        reason = arguments["reason"]

        # Resolve NPC
        npc_slug, npc_data = resolve_npc_by_keyword(campaign_id, npc_name)
        if not npc_data:
            return [TextContent(
                type="text",
                text=err_not_found("NPC", npc_name, "Use NPC name or keyword.")
            )]

        resolved_name = npc_data.get("name", npc_name)

        # Initialize if needed (backwards compat)
        if "todos" not in npc_data:
            npc_data["todos"] = []
        if "insights" not in npc_data:
            npc_data["insights"] = []

        # Find the todo
        todo_idx, todo = _find_todo_by_name(npc_data["todos"], todo_name)
        if todo is None:
            available = ", ".join([t["name"] for t in npc_data["todos"]]) or "none"
            return [TextContent(
                type="text",
                text=f"Todo '{todo_name}' not found for {resolved_name}. Available: {available}"
            )]

        # Remove todo from list
        npc_data["todos"].pop(todo_idx)

        # Add insight to NPC
        npc_insight = f"Abandoned '{todo['name']}' (from {todo['source']}): {reason}"
        npc_data["insights"].append(npc_insight)

        npc_repo.save_npc(campaign_id, npc_slug, npc_data)

        result_lines = [
            f"{resolved_name} abandoned '{todo['name']}'.",
            f"Reason: {reason}",
            f"Insight added to {resolved_name}."
        ]

        # If source was NPC, add insight to them
        if todo["source_is_npc"]:
            source_insight = f"{resolved_name} was asked to '{todo['name']}' but abandoned it: {reason}"
            if add_npc_insight(campaign_id, todo["source"], source_insight):
                result_lines.append(f"Insight added to {todo['source']}.")
            else:
                result_lines.append(f"({todo['source']} no longer exists - no insight added)")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error abandoning todo: {str(e)}")]
