# RPG MCP API

FastAPI-based SSE transport for the RPG MCP Server.

## Setup

1. Install dependencies:
```bash
cd api
uv venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
uv pip install -e .
```

2. Create `.env` file:
```bash
cp .env.example .env
# Edit .env and set your API_KEY
```

3. Run the server:
```bash
uvicorn main:app --reload
```

## Authentication

This API uses API key authentication. Include your key in requests:
```bash
curl -H "X-API-Key: your-secret-key" http://localhost:8000/sse
```

## Environment Variables

- `API_KEY` - Secret key for API authentication (required)
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `MCP_SERVER_PATH` - Path to MCP server module
- `ALLOWED_ORIGINS` - CORS allowed origins
