import json

from mcp.types import Resource

from utils import CAMPAIGNS_DIR


async def list_resources() -> list[Resource]:
    """List available resources dynamically."""
    resources = [
        Resource(
            uri="campaign://list",
            name="Campaign List",
            description="List of all available campaigns",
            mimeType="application/json"
        )
    ]

    # Add campaign.json files as resources
    if CAMPAIGNS_DIR.exists():
        for campaign_dir in CAMPAIGNS_DIR.iterdir():
            if campaign_dir.is_dir():
                campaign_file = campaign_dir / "campaign.json"
                if campaign_file.exists():
                    campaign_data = json.loads(campaign_file.read_text())
                    campaign_name = campaign_data.get("name", campaign_dir.name)

                    # Add campaign.json file
                    resources.append(Resource(
                        uri=f"campaign://{campaign_dir.name}/campaign.json",
                        name=f"{campaign_name}",
                        description=f"Campaign data for {campaign_name}",
                        mimeType="application/json"
                    ))

                    # Add combat-current.json if it exists (active combat state)
                    combat_file = campaign_dir / "combat-current.json"
                    if combat_file.exists():
                        resources.append(Resource(
                            uri=f"campaign://{campaign_dir.name}/combat-current.json",
                            name=f"{campaign_name} - Active Combat",
                            description=f"Current combat participants and their states in {campaign_name}",
                            mimeType="application/json"
                        ))

                    # Add npcs.json if it exists (NPC index with keywords)
                    npcs_index_file = campaign_dir / "npcs.json"
                    if npcs_index_file.exists():
                        resources.append(Resource(
                            uri=f"campaign://{campaign_dir.name}/npcs.json",
                            name=f"{campaign_name} - NPC Index",
                            description=f"List of all NPCs with keywords in {campaign_name}",
                            mimeType="application/json"
                        ))

                    # Add bestiary.json if it exists (enemy templates)
                    bestiary_file = campaign_dir / "bestiary.json"
                    if bestiary_file.exists():
                        resources.append(Resource(
                            uri=f"campaign://{campaign_dir.name}/bestiary.json",
                            name=f"{campaign_name} - Bestiary",
                            description=f"Enemy templates with stats and weapons in {campaign_name}",
                            mimeType="application/json"
                        ))

                    # Add all individual NPC files
                    for npc_file in campaign_dir.glob("npc-*.json"):
                        npc_data = json.loads(npc_file.read_text())
                        npc_name = npc_data.get("name", npc_file.stem.replace("npc-", ""))
                        resources.append(Resource(
                            uri=f"campaign://{campaign_dir.name}/{npc_file.name}",
                            name=f"{campaign_name} - {npc_name}",
                            description=f"Full stats and info for {npc_name}",
                            mimeType="application/json"
                        ))

    return resources


async def read_resource(uri: str) -> str:
    """Read resource content by URI."""

    # Convert AnyUrl to string
    uri = str(uri)

    if uri == "campaign://list":
        # Return list of all campaigns
        campaigns = []
        if CAMPAIGNS_DIR.exists():
            for campaign_dir in CAMPAIGNS_DIR.iterdir():
                if campaign_dir.is_dir():
                    campaign_file = campaign_dir / "campaign.json"
                    if campaign_file.exists():
                        campaign_data = json.loads(campaign_file.read_text())
                        campaigns.append({
                            "id": campaign_data.get("id"),
                            "name": campaign_data.get("name"),
                            "slug": campaign_dir.name
                        })
        return json.dumps(campaigns, indent=2)

    # Parse campaign URIs: campaign://{slug}/ or campaign://{slug}/{file}
    if uri.startswith("campaign://"):
        path_parts = uri.replace("campaign://", "").strip("/").split("/")

        if len(path_parts) == 1:
            # campaign://{slug}/ - list files in campaign
            campaign_slug = path_parts[0]
            campaign_dir = CAMPAIGNS_DIR / campaign_slug

            if not campaign_dir.exists():
                return json.dumps({"error": f"Campaign not found: {campaign_slug}"})

            files = [f.name for f in campaign_dir.glob("*.json")]
            return json.dumps({"campaign": campaign_slug, "files": files}, indent=2)

        elif len(path_parts) == 2:
            # campaign://{slug}/{file} - read file content
            campaign_slug, filename = path_parts
            file_path = CAMPAIGNS_DIR / campaign_slug / filename

            if not file_path.exists():
                return json.dumps({"error": f"File not found: {filename}"})

            return file_path.read_text()

    return json.dumps({"error": f"Unknown resource: {uri}"})
