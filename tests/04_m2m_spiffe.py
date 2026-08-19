"""
04 — M2M Authentication: SPIFFE/SPIRE (Method C)
Acquires token via JWT-SVID from SPIRE agent — zero stored credentials.
Docs: https://docs.authsec.dev/sdk/python/m2m/spiffe

NOTE: This script runs ONLY inside a Kubernetes pod with SPIRE agent socket mounted.
      Deploy with: kubectl apply -f k8s-spiffe/04-workload.yaml
      Run with:    kubectl exec spiffe-test -- python /app/test_spiffe.py
"""
import asyncio, os, sys

PASS = "\033[92m PASS \033[0m"
FAIL = "\033[91m FAIL \033[0m"


async def main():
    from authsec_sdk import SpiffeWorkloadIdentity, SpiffeConfig
    import httpx

    CLIENT_ID = os.environ["SPIFFE_CLIENT_ID"]
    SPIFFE_ID = os.environ["SPIFFE_ID"]
    MCP_URL = os.environ["MCP_URL"]
    SCOPES = "mcp_prod:read mcp_prod:tools:read"

    print()
    print("  +----------------------------------------------------------+")
    print("  |   04  M2M SPIFFE/SPIRE (Method C)                        |")
    print("  +----------------------------------------------------------+")
    print()
    print(f"  Client ID    {CLIENT_ID}")
    print(f"  SPIFFE ID    {SPIFFE_ID}")
    print(f"  MCP Server   {MCP_URL}")
    print(f"  Socket       /run/spire/sockets/agent.sock")
    print(f"  Scopes       {SCOPES}")
    print(f"  Method       JWT-SVID (zero stored credentials)")
    print()

    results = []

    # ── Step 1: Get token via SVID ──
    print("  [1/3] Connecting to SPIRE agent and requesting JWT-SVID...")
    spiffe = SpiffeWorkloadIdentity(SpiffeConfig(
        mcp_server_url=MCP_URL,
        client_id=CLIENT_ID,
        spiffe_id=SPIFFE_ID,
        scopes=SCOPES,
    ))
    async with spiffe:
        token = await spiffe.access_for()

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

        # ── Step 3: tools/call add_no ──
        print("  [3/3] Calling add_no(2, 3)...")
        r = await c.post(MCP_URL, headers=headers,
                         json={"jsonrpc": "2.0", "method": "tools/call", "id": 2,
                               "params": {"name": "add_no", "arguments": {"a": 2, "b": 3}}})
        data = r.json()
        result_text = ""
        if "result" in data and not data["result"].get("isError"):
            result_text = data["result"]["content"][0]["text"]
        ok = result_text.strip() == "5.0"
        results.append(ok)
        print(f"        {PASS if ok else FAIL}  add_no(2,3) = {result_text}")
        print()

    # ── Summary ──
    passed = sum(results)
    total = len(results)
    tag = PASS if passed == total else FAIL
    print(f"  Result: {tag}  {passed}/{total} checks passed")
    print()


asyncio.run(main())
