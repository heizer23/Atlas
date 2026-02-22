"""
Quick smoke test for the local MCP server.
Run:  python test_local.py
Requires: pip install httpx fastmcp
"""
import httpx, json

BASE = "http://localhost:8002/mcp"

def mcp_call(payload, session_id=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["mcp-session-id"] = session_id
    r = httpx.post(BASE, json=payload, headers=headers, timeout=10)
    sid = r.headers.get("mcp-session-id", session_id)
    # Response may be SSE (data: {...}) or plain JSON
    text = r.text.strip()
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip()), sid
    return r.json(), sid


def call_tool(name, args, session_id):
    result, _ = mcp_call(
        {"jsonrpc": "2.0", "id": 99, "method": "tools/call",
         "params": {"name": name, "arguments": args}},
        session_id,
    )
    content = result.get("result", {}).get("content", [{}])
    return content[0].get("text", "???") if content else "???"


def run():
    print("=" * 50)
    print("MCP Server smoke test")
    print("=" * 50)

    # 1. Initialize
    init, sid = mcp_call({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smoke-test", "version": "1.0"}
        }
    })
    server_info = init.get("result", {}).get("serverInfo", {})
    print(f"✅ Connected  │ server: {server_info}")
    print(f"   Session ID: {sid}")
    print()

    # 2. List tools
    tools_res, _ = mcp_call(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, sid
    )
    tools = tools_res.get("result", {}).get("tools", [])
    print(f"✅ Tools found: {[t['name'] for t in tools]}")
    print()

    # 3. Test tool calls
    tests = [
        ("apple",  "red"),
        ("banana", "yellow"),
        ("mango",  "orange"),
        ("APPLE",  "red"),         # case-insensitive
        ("kiwi",   None),          # unknown → error message
    ]

    all_passed = True
    for fruit, expected_color in tests:
        result = call_tool("get_fruit_color", {"fruit": fruit}, sid)
        if expected_color:
            passed = result == expected_color
            icon = "✅" if passed else "❌"
            print(f"{icon} get_fruit_color({fruit!r:8}) → {result!r}  (expected {expected_color!r})")
            if not passed:
                all_passed = False
        else:
            # Unknown fruit: expect an error message string
            passed = "Unknown" in result
            icon = "✅" if passed else "❌"
            print(f"{icon} get_fruit_color({fruit!r:8}) → {result!r}  (expected unknown-fruit message)")
            if not passed:
                all_passed = False

    print()
    print("=" * 50)
    print("ALL TESTS PASSED ✅" if all_passed else "SOME TESTS FAILED ❌")
    print("=" * 50)


if __name__ == "__main__":
    run()
