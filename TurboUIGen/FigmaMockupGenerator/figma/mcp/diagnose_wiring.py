#!/usr/bin/env python3
"""
Diagnose Figma wiring by running JS directly via figma_execute_js.
Usage: python diagnose_wiring.py
"""
import json, urllib.request, time

MCP = "http://localhost:7771"

def call_tool(name, args={}):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": args}
    }).encode()
    req = urllib.request.Request(
        f"{MCP}/mcp", data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}

def run_js(js):
    """Run JS and wait briefly for Figma to process it."""
    result = call_tool("figma_execute_js", {"code": js})
    time.sleep(0.5)
    return result

print("=" * 60)
print("  Figma Wiring Diagnostic")
print("=" * 60)

# 1. Frames
print("\n[1] Frames on canvas:")
r = run_js("""
(async () => {
  var out = figma.currentPage.children.map(function(f) {
    return f.name + ' (' + f.type + ') ' + f.width + 'x' + f.height;
  });
  figma.notify('Diagnostic: ' + out.length + ' frames found', {timeout: 3000});
  return JSON.stringify(out);
})();
""")
if isinstance(r, list):
    for f in r: print(f"  {f}")
else:
    print(f"  {r}")
    print("  NOTE: 'ok:true' means JS ran but no return value captured — this is a")
    print("  figma-console-mcp limitation. Check Figma for the notify() popup.")

# 2. Reactions — write to console.log via figma.notify (visible in Figma)
print("\n[2] Checking reactions (watch for Figma notifications):")
r = run_js("""
(async () => {
  var count = 0;
  var details = [];
  function walk(node) {
    if (node.reactions && node.reactions.length > 0) {
      count++;
      node.reactions.forEach(function(rx) {
        var a = (rx.actions && rx.actions[0]) || {};
        details.push(node.name + ':' + (a.navigation||'?'));
      });
    }
    if (node.children) node.children.forEach(walk);
  }
  figma.currentPage.children.forEach(walk);
  var msg = count + ' reactions. ' + details.slice(0,5).join(', ');
  figma.notify(msg, {timeout: 8000});
  return JSON.stringify({count: count, details: details});
})();
""")
if isinstance(r, dict) and "count" in r:
    print(f"  Reactions found: {r['count']}")
    for d in r.get("details", []):
        print(f"    {d}")
else:
    print(f"  Result: {r}")
    print("  → Check Figma Desktop for a notification showing reaction count")

# 3. Prototype start
print("\n[3] Prototype start node:")
r = run_js("""
(async () => {
  var s = figma.currentPage.prototypeStartNode;
  return JSON.stringify(s ? {name: s.name, set: true} : {name: null, set: false});
})();
""")
if isinstance(r, dict):
    print(f"  Start: {r.get('name', 'NOT SET')} (set={r.get('set', False)})")
else:
    print(f"  {r}")

print("\n" + "=" * 60)
print("  IMPORTANT: Since figma-console-mcp does not return JS values,")
print("  check Figma Desktop for notify() popups showing the results.")
print("=" * 60)
