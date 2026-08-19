"""
03 — M2M Authentication: Private-key JWT (Method B)
Acquires token by signing a JWT assertion with an RSA private key.
Docs: https://docs.authsec.dev/sdk/python/m2m/private-key-jwt
"""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

PASS = "\033[92m PASS \033[0m"
FAIL = "\033[91m FAIL \033[0m"


async def main():
    from authsec_sdk import AgentIdentity, PrivateKeyJwtAuth
    import httpx

    ISSUER = os.environ["AUTHSEC_ISSUER"]
    CLIENT_ID = os.environ["PK_CLIENT_ID"]
    KEY_PATH = os.environ["PK_PRIVATE_KEY_PATH"]
    KID = os.environ["PK_KID"]
    MCP_URL = os.environ["MCP_URL"]
    SCOPES = ["mcp_prod:read", "mcp_prod:tools:read"]

    print()
    print("  +----------------------------------------------------------+")
    print("  |   03  M2M Private-key JWT (Method B)                     |")
    print("  +----------------------------------------------------------+")
    print()
    print(f"  Issuer       {ISSUER}")
    print(f"  Client ID    {CLIENT_ID}")
    print(f"  Key ID       {KID}")
    print(f"  Key Path     {KEY_PATH}")
    print(f"  MCP Server   {MCP_URL}")
    print(f"  Scopes       {', '.join(SCOPES)}")
    print()

    results = []

    # ── Step 1: Acquire token ──
    print("  [1/3] Acquiring token via signed JWT assertion...")
    agent = AgentIdentity(
        ISSUER,
        CLIENT_ID,
        auth=PrivateKeyJwtAuth(KEY_PATH, kid=KID),
    )
    async with agent:
        token = await agent.access_for(
            MCP_URL,
            requested_scopes=SCOPES,
        )

    ok = bool(token and len(token) > 20)
    results.append(ok)
    print(f"        {PASS if ok else FAIL}  Token acquired ({len(token)} chars)")
    print()
    print(f"  Token: {token}")
    print()

    # ── Step 2: tools/list ──
    print("  [2/3] Calling tools/list...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(MCP_URL, headers=headers,
                         json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        data = r.json()
        tools = data.get("result", {}).get("tools", [])
        ok = r.status_code == 200 and len(tools) > 0
        results.append(ok)
        print(f"        {PASS if ok else FAIL}  Status {r.status_code} — {len(tools)} tools found")
        for t in tools:
            print(f"          - {t['name']}: {t.get('description', '')}")
        print()

        # ── Step 3: tools/call multiply_no ──
        print("  [3/3] Calling multiply_no(4, 5)...")
        r = await c.post(MCP_URL, headers=headers,
                         json={"jsonrpc": "2.0", "method": "tools/call", "id": 2,
                               "params": {"name": "multiply_no", "arguments": {"a": 4, "b": 5}}})
        data = r.json()
        result_text = ""
        if "result" in data and not data["result"].get("isError"):
            result_text = data["result"]["content"][0]["text"]
        ok = result_text.strip() == "20.0"
        results.append(ok)
        print(f"        {PASS if ok else FAIL}  multiply_no(4,5) = {result_text}")
        print()

    # ── Summary ──
    passed = sum(results)
    total = len(results)
    tag = PASS if passed == total else FAIL
    print(f"  Result: {tag}  {passed}/{total} checks passed")
    print()


asyncio.run(main())
