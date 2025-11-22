# RPG MCP API

FastAPI wrapper for RPG MCP Server. Exposes D&D-style combat tools via HTTP/SSE for Claude.ai Web.

## Run It

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Connect to Claude.ai

**Local testing:** Use ngrok or cloudflare tunnel
```bash
ngrok http 8000
# Add the https URL to Claude.ai → Settings → Custom Connectors
```

**Production:** Deploy to Railway, add Railway URL to Custom Connectors

## What You Get

11 tools: campaign creation, NPCs, bestiary, combat, resource readers

**Threat levels** (creature hit chance):
- `none` 10% | `negligible` 25% | `low` 35% | `moderate` 50%
- `high` 65% | `deadly` 80% | `certain_death` 95%

## Deployment

Railway:
1. Connect repo
2. Add volume: `/app/mcp_src/campaigns`
3. Deploy

## Swap to Database

```python
# tools/combat.py
from repository_json import JsonCombatRepository  # ← current
from repository_db import DbCombatRepository      # ← swap to this
```

See `repository_db_example.py` for template.

## License

MIT
