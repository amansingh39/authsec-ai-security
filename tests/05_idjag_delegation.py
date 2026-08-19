"""
05 — ID-JAG Delegation
User logs in via browser, agent acts on their behalf with delegated token, then calls MCP tools.
Docs: https://docs.authsec.dev/sdk/python/idjag-delegation
"""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

PASS = "\033[92m PASS \033[0m"
FAIL = "\033[91m FAIL \033[0m"


async def main():
    from authsec_sdk import (
        AgentIdentity, browser_login,
        PendingApprovalError, ApprovalDeniedError, poll_until_approved,
    )
    import httpx

    ISSUER = os.environ["AUTHSEC_ISSUER"]
    CLIENT_ID = os.environ["AGENT_CLIENT_ID"]
    CLIENT_SECRET = os.environ["AGENT_CLIENT_SECRET"]
    MCP_URL = os.environ["MCP_URL"]
    SCOPES = ["mcp_prod:read", "mcp_prod:tools:read"]

    print()
    print("  +----------------------------------------------------------+")
    print("  |   05  ID-JAG Delegation                                  |")
    print("  +----------------------------------------------------------+")
    print()
    print(f"  Issuer       {ISSUER}")
    print(f"  Agent ID     {CLIENT_ID}")
    print(f"  MCP Server   {MCP_URL}")
    print(f"  Scopes       {', '.join(SCOPES)}")
    print()

    results = []

    # ── Step 1: Browser login ──
    print("  [1/4] Opening browser for user login...")
    id_token = await browser_login(
        issuer=ISSUER,
        client_id=CLIENT_ID,
        resource=MCP_URL,
    )
    ok = bool(id_token and len(id_token) > 20)
    results.append(ok)
    print(f"        {PASS if ok else FAIL}  id_token received ({len(id_token)} chars)")
    print()
    print(f"  ID Token: {id_token}")
    print()

    # ── Step 2: Exchange for delegated access token ──
    print("  [2/4] Exchanging id_token for delegated access token...")
    agent = AgentIdentity(
        issuer=ISSUER,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        idp_issuer=ISSUER,
    )
    async with agent:
        try:
            token = await agent.access_for(
                MCP_URL,
                user_session={"subject_token": id_token},
                requested_scopes=SCOPES,
            )
        except PendingApprovalError as e:
            print("        Waiting for admin approval...")
            token = await poll_until_approved(
                agent, MCP_URL, e.status_url,
                user_session={"subject_token": id_token},
                requested_scopes=SCOPES,
            )
        except ApprovalDeniedError:
            print(f"        {FAIL}  Admin denied access")
            return

    ok = bool(token and len(token) > 20)
    results.append(ok)
    print(f"        {PASS if ok else FAIL}  Delegated token acquired ({len(token)} chars)")
    print()
    print(f"  Access Token: {token}")
    print()

    # ── Step 3: tools/list ──
    print("  [3/4] Calling tools/list...")
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

        # ── Step 4: tools/call add_no ──
        print("  [4/4] Calling add_no(10, 20)...")
        r = await c.post(MCP_URL, headers=headers,
                         json={"jsonrpc": "2.0", "method": "tools/call", "id": 2,
                               "params": {"name": "add_no", "arguments": {"a": 10, "b": 20}}})
        data = r.json()
        result_text = ""
        if "result" in data and not data["result"].get("isError"):
            result_text = data["result"]["content"][0]["text"]
        ok = result_text.strip() == "30.0"
        results.append(ok)
        print(f"        {PASS if ok else FAIL}  add_no(10,20) = {result_text}")
        print()

    # ── Summary ──
    passed = sum(results)
    total = len(results)
    tag = PASS if passed == total else FAIL
    print(f"  Result: {tag}  {passed}/{total} checks passed")
    print()


asyncio.run(main())
