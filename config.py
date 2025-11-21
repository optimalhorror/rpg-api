"""Configuration management for the API server."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""

    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # CORS settings
    ALLOWED_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]

    # MCP Server path
    MCP_SERVER_PATH: Path = Path(os.getenv("MCP_SERVER_PATH", "./mcp"))

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        # No validation needed for now
        # Security handled at deployment level (IP whitelist)
        pass


# Validate config on import
Config.validate()
