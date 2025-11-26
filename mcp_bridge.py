"""Bridge between FastAPI HTTP/SSE and MCP stdio server."""
import sys
from pathlib import Path

# Import directly from MCP server modules
sys.path.insert(0, str(Path(__file__).parent / "mcp_src" / "src"))

from tools import get_all_tools, get_tool_handlers
from resources import list_resources as mcp_list_resources, read_resource as mcp_read_resource


class MCPBridge:
    """
    Bridge to handle MCP protocol over HTTP/SSE.

    Since the MCP server is designed for stdio, we call the tool
    handlers directly rather than going through the Server protocol.
    """

    def __init__(self):
        # Auto-discover from registry
        self.tool_handlers = get_tool_handlers()
        self.tool_definitions = {tool.name: tool for tool in get_all_tools()}

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
                "uri": str(resource.uri),
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
            "mimeType": "application/json",
            "text": content
        }


# Global bridge instance
bridge = MCPBridge()
