"""RPG MCP Server - Main package initialization."""
import sys
from pathlib import Path

# Add src directory to Python path once at package level
# This allows all submodules to import from the src root without duplication
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


def hello() -> str:
    return "Hello from rpg-mcp-server!"
