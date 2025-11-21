"""Bridge between FastAPI HTTP/SSE and MCP stdio server."""
import sys
from pathlib import Path

# Import directly from MCP server modules
sys.path.insert(0, str(Path(__file__).parent / "mcp_src" / "src"))

from tools import (
    get_begin_campaign_tool,
    handle_begin_campaign,
    get_create_npc_tool,
    handle_create_npc,
    get_attack_tool,
    handle_attack,
    get_remove_from_combat_tool,
    handle_remove_from_combat,
    get_create_bestiary_entry_tool,
    handle_create_bestiary_entry,
)
from resources import list_resources as mcp_list_resources, read_resource as mcp_read_resource


class MCPBridge:
    """
    Bridge to handle MCP protocol over HTTP/SSE.

    Since the MCP server is designed for stdio, we call the tool
    handlers directly rather than going through the Server protocol.
    """

    def __init__(self):
        # Map of tool names to their handlers
        self.tool_handlers = {
            "begin_campaign": handle_begin_campaign,
            "create_npc": handle_create_npc,
            "attack": handle_attack,
            "remove_from_combat": handle_remove_from_combat,
            "create_bestiary_entry": handle_create_bestiary_entry,
        }

        # Map of tool names to their definitions
        self.tool_definitions = {
            "begin_campaign": get_begin_campaign_tool(),
            "create_npc": get_create_npc_tool(),
            "attack": get_attack_tool(),
            "remove_from_combat": get_remove_from_combat_tool(),
            "create_bestiary_entry": get_create_bestiary_entry_tool(),
        }

    async def list_tools(self):
        """Get list of available tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            }
            for tool in self.tool_definitions.values()
        ]

    async def call_tool(self, tool_name: str, arguments: dict):
        """Call a tool by name."""
        if tool_name not in self.tool_handlers:
            raise ValueError(f"Unknown tool: {tool_name}")

        handler = self.tool_handlers[tool_name]
        result = await handler(arguments)

        return [
            {
                "type": content.type,
                "text": content.text
            }
            for content in result
        ]

    async def list_resources(self):
        """Get list of available resources."""
        resources = await mcp_list_resources()
        return [
            {
                "uri": resource.uri,
                "name": resource.name,
                "description": resource.description,
                "mimeType": resource.mimeType
            }
            for resource in resources
        ]

    async def read_resource(self, uri: str):
        """Read a resource by URI."""
        content = await mcp_read_resource(uri)
        return {
            "uri": uri,
            "text": content
        }


# Global bridge instance
bridge = MCPBridge()
