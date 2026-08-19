"""
01 — Protect MCP Server
Verifies the server is running, PRM metadata is published, and unauthenticated requests are rejected.
Docs: https://docs.authsec.dev/sdk/python/protect-mcp-server
"""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

MCP_URL = os.environ["MCP_URL"]
BASE_URL = MCP_URL.rsplit("/", 1)[0]
PRM_URL = f"{BASE_URL}/.well-known/oauth-protected-resource/mcp"

PASS = "\033[92m PASS \033[0m"
FAIL = "\033[91m FAIL \033[0m"


async def main():
    import httpx

    print()
    print("  +----------------------------------------------------------+")
    print("  |   01  Protect MCP Server                                 |")
    print("  +----------------------------------------------------------+")
    print()
    print(f"  MCP Server   {MCP_URL}")
    print(f"  PRM URL      {PRM_URL}")
    print()

    results = []
    async with httpx.AsyncClient(timeout=30) as c:

        # ── Test 1: PRM metadata ──
        print("  [1/3] Checking PRM metadata endpoint...")
        r = await c.get(PRM_URL)
        ok = r.status_code == 200
        results.append(ok)
        if ok:
            data = r.json()
            print(f"        {PASS}  Status {r.status_code}")
            print(f"        resource           {data.get('resource', '?')}")
            print(f"        authorization_servers  {data.get('authorization_servers', '?')}")
            scopes = data.get("scopes_supported", [])
            print(f"        scopes_supported   {', '.join(scopes)}")
        else:
            print(f"        {FAIL}  Status {r.status_code}")
        print()

        # ── Test 2: Unauthenticated → 401 ──
        print("  [2/3] Sending unauthenticated request (expect 401)...")
        r = await c.post(
            MCP_URL,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
        )
        ok = r.status_code == 401
        results.append(ok)
        print(f"        {''+PASS if ok else FAIL}  Status {r.status_code}")
        print()

        # ── Test 3: Invalid token → 401 ──
        print("  [3/3] Sending invalid bearer token (expect 401)...")
        r = await c.post(
            MCP_URL,
            headers={
                "Authorization": "Bearer invalid-token-xxx",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
        )
        ok = r.status_code == 401
        results.append(ok)
        print(f"        {''+PASS if ok else FAIL}  Status {r.status_code}")
        print()

    # ── Summary ──
    passed = sum(results)
    total = len(results)
    tag = PASS if passed == total else FAIL
    print(f"  Result: {tag}  {passed}/{total} checks passed")
    print()


asyncio.run(main())
