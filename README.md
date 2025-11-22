# RPG MCP API

FastAPI-based HTTP/SSE transport for the [RPG MCP Server](https://github.com/optimalhorror/rpg-mcp-server).

Provides HTTP endpoints for Claude.ai Web to connect and run D&D-style campaigns remotely.

## Features

- **MCP Streamable HTTP** - Full MCP protocol over HTTP/SSE (2025-03-26 spec)
- **11 Tools** - Campaign management, NPCs, bestiary, combat, resource readers
- **Threat Level System** - Creatures with dynamic hit chances (10% → 95%)
- **Repository Pattern** - Clean abstraction for swapping JSON → database
- **No Authentication** - Security via IP whitelist on Railway
- **Persistent Storage** - Railway volume for campaign data

## Quick Start

1. **Install dependencies:**
```bash
uv venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
uv pip install -r requirements.txt
```

2. **Run locally:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

3. **Connect from Claude.ai:**
   - Go to Claude.ai → Settings → Custom Connectors
   - Add: `http://localhost:8000/`
   - Start using RPG tools!

## MCP Endpoints

The server implements **MCP Streamable HTTP** protocol:

- `GET /` or `GET /mcp` - SSE stream for server messages
- `POST /` or `POST /mcp` - JSON-RPC 2.0 for tool calls

Both endpoints support:
- `initialize` - Protocol handshake
- `tools/list` - Get available tools
- `tools/call` - Execute tools
- `resources/list` - Get available resources
- `resources/read` - Read resource data

## Tools Available

### Core Tools (5)
- `begin_campaign` - Create new campaign with player
- `create_npc` - Add NPC with optional `hit_chance` (default 50%)
- `create_bestiary_entry` - Add creatures with mandatory `threat_level`
- `attack` - Combat with dynamic hit chance based on attacker
- `remove_from_combat` - Remove from combat (death/flee/surrender)

### Resource Readers (6)
- `list_campaigns` - List all campaigns
- `get_campaign` - Get campaign details
- `list_npcs` - List NPCs in campaign
- `get_npc` - Get NPC stats
- `get_combat_status` - View active combat
- `get_bestiary` - View creature templates

## Threat Levels

Bestiary entries require `threat_level` (determines hit chance):

| Level | Hit % | Example |
|-------|-------|---------|
| `none` | 10% | Fly |
| `negligible` | 25% | Dog |
| `low` | 35% | Wolf |
| `moderate` | 50% | Bandit |
| `high` | 65% | Mercenary |
| `deadly` | 80% | Dragon |
| `certain_death` | 95% | Eldritch horror |

## Examples

**Create bestiary entry:**
```json
POST /mcp
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "create_bestiary_entry",
    "arguments": {
      "campaign_id": "abc123",
      "name": "Giant Rat",
      "threat_level": "negligible",
      "hp": "3",
      "weapons": {"bite": "1d4"}
    }
  }
}
```

**Combat with dynamic hit chance:**
```json
POST /mcp
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "attack",
    "arguments": {
      "campaign_id": "abc123",
      "attacker": "Dave",
      "target": "Giant Rat",
      "weapon": "sword"
    }
  }
}
```
→ Giant Rat has 25% hit chance (negligible threat)
→ Dave has 50% hit chance (default NPC)

## Repository Pattern

Data persistence is abstracted via repositories:

```python
# Current: JSON files
from repository_json import JsonNPCRepository
_npc_repo = JsonNPCRepository()

# Future: Swap to database
from repository_db import DbNPCRepository
_npc_repo = DbNPCRepository()
```

See `mcp_src/src/repository_db_example.py` for DB implementation template.

## Deployment

### Railway (Recommended)

1. **Create Railway project**
2. **Connect GitHub repo**
3. **Add Volume:**
   - Mount path: `/app/mcp_src/campaigns`
   - Size: 1GB
4. **Set IP Whitelist** in Railway settings
5. **Deploy!**

The `Procfile` tells Railway how to start:
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Environment Variables

Optional (defaults work fine):
- `HOST` - Server host (default: `0.0.0.0`)
- `PORT` - Server port (default: `8000`)
- `MCP_SERVER_PATH` - Path to MCP code (default: `./mcp_src`)
- `ALLOWED_ORIGINS` - CORS origins (default: `*`)

## Project Structure

```
rpg-api/
├── main.py                    # FastAPI app + MCP endpoints
├── mcp_bridge.py              # Bridge to MCP server
├── config.py                  # Configuration
├── requirements.txt           # Python deps
├── Procfile                   # Railway startup
├── sync-mcp.sh               # Sync script (private → public)
└── mcp_src/src/              # MCP server source
    ├── repository.py          # Abstract interfaces
    ├── repository_json.py     # JSON implementation
    ├── repository_db_example.py  # DB template
    ├── resources.py           # MCP resources
    ├── utils.py               # Utilities
    └── tools/                 # Tool implementations
        ├── campaign.py        # Campaign creation
        ├── npc.py             # NPC management
        ├── bestiary.py        # Creature templates
        ├── combat.py          # Combat system
        └── readers.py         # Resource readers
```

## Security

**No built-in auth** - secure at infrastructure level:

**IP Whitelist** (Railway) - Recommended
**VPN/Tunnel** (Tailscale, Cloudflare)
**Reverse Proxy** (Caddy, Nginx with auth)

## Syncing with Public MCP Repo

Use the sync script to copy core MCP code to the public repo:

```bash
./sync-mcp.sh
```

This copies `repository*.py` and `tools/*.py` from `mcp_src/` to `../rpg-mcp-server/src/`.

## License

MIT
