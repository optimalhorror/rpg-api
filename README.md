# RPG MCP API

FastAPI-based HTTP/SSE transport for the [RPG MCP Server](https://github.com/optimalhorror/rpg-mcp-server).

## Features

- **Full MCP Integration** - All RPG tools and resources accessible via HTTP
- **RESTful API** - Simple HTTP endpoints for tools and resources
- **SSE Support** - Server-Sent Events for streaming (MCP protocol ready)
- **No Authentication** - Security via IP whitelist at deployment level
- **Embedded MCP Server** - MCP server source included directly

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/rpg-api.git
cd rpg-api
```

2. Install dependencies:
```bash
uv venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
uv pip install fastapi uvicorn python-dotenv mcp
```

3. (Optional) Create `.env` file:
```bash
cp .env.example .env
# Defaults work fine for local development
```

4. Run the server:
```bash
uv run python main.py
```

Server runs on `http://localhost:8000`

## API Endpoints

### Health Check
```bash
GET /
```
Returns server status.

### Tools

**List all tools:**
```bash
GET /tools
```

**Call a tool:**
```bash
POST /tools/{tool_name}
Content-Type: application/json

{
  "name": "Campaign Name",
  "player_name": "Hero"
}
```

Available tools:
- `begin_campaign` - Create new campaign
- `create_npc` - Add NPC to campaign
- `create_bestiary_entry` - Create enemy template
- `attack` - Perform combat action
- `remove_from_combat` - Remove participant from combat

### Resources

**List all resources:**
```bash
GET /resources
```

**Read a resource:**
```bash
GET /resources/campaign://list
GET /resources/campaign://my-campaign/campaign.json
```

### MCP Protocol

**SSE endpoint** (for streaming):
```bash
GET /sse
```

**JSON-RPC messages** (for full MCP protocol):
```bash
POST /messages
```

## Examples

**Start a new campaign:**
```bash
curl -X POST http://localhost:8000/tools/begin_campaign \
  -H "Content-Type: application/json" \
  -d '{
    "name": "The Lost Kingdom",
    "player_name": "Aragorn",
    "player_description": "A brave ranger from the North",
    "player_health": 25,
    "player_weapons": {"sword": "1d8", "bow": "1d6"}
  }'
```

**List all campaigns:**
```bash
curl http://localhost:8000/resources
```

**Get campaign data:**
```bash
curl http://localhost:8000/resources/campaign://the-lost-kingdom/campaign.json
```

## Environment Variables

- `HOST` - Server host (default: `0.0.0.0`)
- `PORT` - Server port (default: `8000`)
- `MCP_SERVER_PATH` - Path to MCP server (default: `./mcp`)
- `ALLOWED_ORIGINS` - CORS origins, comma-separated (optional)

## Deployment

### Security
This API has **no built-in authentication**. Secure it at the infrastructure level:

1. **IP Whitelist** - Allow only your IP (Railway, Fly.io, etc.)
2. **VPN/Tunnel** - Use Tailscale or Cloudflare Tunnel
3. **Reverse Proxy** - Add auth via Caddy/Nginx

### Railway
```bash
# Deploy to Railway
railway init
railway up

# Set environment in Railway dashboard:
# - Add your IP to whitelist
```

### Fly.io
```bash
# Deploy to Fly.io
fly launch
fly deploy

# Configure IP whitelist in fly.toml
```

## MCP Server Source

The `mcp/` directory contains a copy of the [RPG MCP Server](https://github.com/optimalhorror/rpg-mcp-server) source code.

To update to the latest version, manually copy from the public repo.

## Development

**Run with auto-reload:**
```bash
uvicorn main:app --reload
```

**Test endpoints:**
```bash
# Health check
curl http://localhost:8000/

# List tools
curl http://localhost:8000/tools | jq

# Create campaign
curl -X POST http://localhost:8000/tools/begin_campaign \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "player_name": "Hero"}'
```

## Project Structure

```
rpg-api/
├── main.py              # FastAPI application
├── mcp_bridge.py        # Bridge to MCP server functions
├── config.py            # Configuration management
├── auth.py              # (unused - for future auth)
├── .env                 # Environment variables (gitignored)
├── .env.example         # Example configuration
├── pyproject.toml       # Python dependencies
└── mcp/                 # MCP server source code
    └── src/
        ├── server.py
        ├── tools/
        └── resources.py
```

## License

MIT
