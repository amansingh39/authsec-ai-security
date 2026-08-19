"""
DeepSeek AI Agent with AuthSec ID-JAG authentication.
Authenticates via browser login, discovers MCP tools, then lets you chat.
Handles token revocation gracefully.
"""
import asyncio, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


async def main():
    from authsec_sdk import (
        AgentIdentity, browser_login,
        PendingApprovalError, poll_until_approved,
    )
    import httpx

    ISSUER = os.environ["AUTHSEC_ISSUER"]
    CLIENT_ID = os.environ["AGENT_CLIENT_ID"]
    CLIENT_SECRET = os.environ["AGENT_CLIENT_SECRET"]
    MCP_URL = os.environ["MCP_URL"]
    DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
    SCOPES = ["mcp_prod:read", "mcp_prod:tools:read", "mcp_prod:tools:write"]

    print()
    print("  +----------------------------------------------------------+")
    print("  |   AuthSec AI Agent (DeepSeek + ID-JAG)                   |")
    print("  +----------------------------------------------------------+")
    print()

    # ── Authenticate ──
    print("  [1/3] Opening browser for login...")
    id_token = await browser_login(issuer=ISSUER, client_id=CLIENT_ID, resource=MCP_URL)
    print("        Login successful")
    print()

    print("  [2/3] Getting delegated access token...")
    agent = AgentIdentity(
        issuer=ISSUER, client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET, idp_issuer=ISSUER,
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
    print("        Token acquired")
    print()

    # ── Discover tools ──
    print("  [3/3] Discovering MCP tools...")
    await asyncio.sleep(1)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(MCP_URL, headers=headers,
                         json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        if r.status_code == 401:
            print("        TOKEN REVOKED — access denied")
            return
        tools_data = r.json().get("result", {}).get("tools", [])

    if not tools_data:
        print("        No tools found")
        return

    deepseek_tools = []
    for t in tools_data:
        schema = t.get("inputSchema", {})
        props = schema.get("properties", {})
        params = {
            "type": "object",
            "properties": props,
            "required": schema.get("required", list(props.keys())),
        }
        deepseek_tools.append({
            "type": "function",
            "function": {"name": t["name"], "description": t.get("description", ""), "parameters": params},
        })
        print(f"        - {t['name']}: {t.get('description', '')}")
    print()

    # ── Chat loop ──
    print("  Ready! Type your questions (Ctrl+C to exit)")
    print("  ─────────────────────────────────────────────")
    print()

    messages = [{"role": "system", "content":
        "You are a helpful assistant with access to MCP tools. "
        "Use them when the user asks for calculations."}]

    while True:
        try:
            user_input = input("  You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Goodbye!")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        async with httpx.AsyncClient(timeout=60) as c:
            # Ask DeepSeek
            r = await c.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": messages, "tools": deepseek_tools},
            )
            reply = r.json()["choices"][0]["message"]
            messages.append(reply)

            # Handle tool calls
            if reply.get("tool_calls"):
                for tc in reply["tool_calls"]:
                    fn = tc["function"]
                    args = json.loads(fn["arguments"])
                    print(f"  [Tool] {fn['name']}({args})")

                    tr = await c.post(MCP_URL, headers=headers, json={
                        "jsonrpc": "2.0", "method": "tools/call", "id": 99,
                        "params": {"name": fn["name"], "arguments": args},
                    })

                    if tr.status_code == 401:
                        print("  TOKEN REVOKED — session ended")
                        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": "Access revoked"})
                        print("  Agent: Your access has been revoked. Please restart.")
                        return

                    td = tr.json()
                    result = td.get("result", {}).get("content", [{}])[0].get("text", str(td))
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

                # Get final response after tool results
                r = await c.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                    json={"model": "deepseek-chat", "messages": messages},
                )
                final = r.json()["choices"][0]["message"]
                messages.append(final)
                print(f"  Agent: {final['content']}")
            else:
                print(f"  Agent: {reply.get('content', '')}")
        print()


asyncio.run(main())
