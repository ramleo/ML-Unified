"""Quick check: connect to the AIRaML MCP server and print its tools, resources and
prompts. Run with your API key in the environment (so it is never typed in a file):

    AIRAML_API_KEY=ak_live_xxx python3 scripts/mcp_list.py

Needs the `fastmcp` package (already in the backend requirements).
"""
import asyncio
import os

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

URL = "https://wram1708-ml-unified.hf.space/mcp/"


async def main() -> None:
    key = os.environ.get("AIRAML_API_KEY")
    if not key:
        raise SystemExit("Set AIRAML_API_KEY=ak_live_… in the environment first.")
    transport = StreamableHttpTransport(URL, headers={"Authorization": f"Bearer {key}"})
    async with Client(transport) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        prompts = await client.list_prompts()
        print(f"\nTOOLS ({len(tools)}):")
        for t in tools:
            print("  -", t.name)
        print(f"\nRESOURCES ({len(resources)}):")
        for r in resources:
            print("  -", r.uri)
        print(f"\nRESOURCE TEMPLATES ({len(templates)}):")
        for t in templates:
            print("  -", t.uri_template)
        print(f"\nPROMPTS ({len(prompts)}):")
        for p in prompts:
            print("  -", p.name)


if __name__ == "__main__":
    asyncio.run(main())
