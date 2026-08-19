#!/usr/bin/env python3
"""
Mobility Global — UI System Builder
=====================================
Creates a complete UI component library in Figma using brand tokens.
Run this once to populate a "UI System" page in your Figma file.

Usage:
    python build_ui_system.py

Prerequisites:
    - MCP server running on port 7771
    - relay.py connected to Figma Desktop
    - Figma Desktop Bridge plugin showing "Local Ready"

Output: A Figma page called "UI System" containing:
    - Color Palette
    - Typography Scale
    - Spacing & Radius
    - Buttons (all variants + states)
    - Form Inputs
    - Dropdowns
    - Tabs
    - Badges / Status Pills
    - Cards
    - KPI Cards
    - Data Table
    - Header
    - Sidebar
    - Footer
    - Alert Banners
    - Modal Dialog
    - Navigation Breadcrumb
    - Pagination
    - Progress Bar
    - Tooltip
    - Avatar
    - Search Bar
"""

import json
import sys
import urllib.request
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
MCP_SERVER = "http://localhost:7771"
TOKENS_FILE = Path(__file__).parent / "brand_tokens.json"

# ── Load brand tokens ──────────────────────────────────────────────────────────
tokens = json.loads(TOKENS_FILE.read_text())
C = tokens["colors"]
U = tokens["usage"]
R = tokens["radius"]
T = tokens["typography"]["sizes"]

# Brand colors (shorthand)
VITAL_BLUE    = U["primary_text"]        # #132445
FORWARD_BLUE  = U["primary_button"]      # #0064D2
MORNING_MIST  = C["primary"]["morning_mist"]  # #B8EAF5
QUIET_LIGHT   = U["page_background"]     # #EFEFE5
WHITE         = "#FFFFFF"
BORDER        = U["border"]              # #E5E7EB
TEXT_PRIMARY  = U["primary_text"]        # #132445
TEXT_SECONDARY= U["secondary_text"]      # #374151
TEXT_MUTED    = U["muted_text"]          # #9CA3AF
STEADY_LILAC  = C["accent"]["steady_lilac"]   # #420E71
SOFT_LILAC    = C["accent"]["soft_lilac"]      # #E3ABFF
VITAL_SPARK   = C["accent"]["vital_spark"]     # #FFE783
CLARITY_YEL   = C["accent"]["clarity_yellow"]  # #FDEBB3
SUCCESS       = C["semantic"]["success"]
SUCCESS_BG    = C["semantic"]["success_bg"]
WARNING       = C["semantic"]["warning"]
WARNING_BG    = C["semantic"]["warning_bg"]
ERROR         = C["semantic"]["error"]
ERROR_BG      = C["semantic"]["error_bg"]

# ── MCP helpers ────────────────────────────────────────────────────────────────
def mcp(method, params={}):
    payload = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    req = urllib.request.Request(f"{MCP_SERVER}/mcp", data=payload,
                                  headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())

def js(code):
    """Run JS in Figma and return result."""
    r = mcp("tools/call", {"name":"figma_execute_js","arguments":{"code":code}})
    text = r.get("result",{}).get("content",[{}])[0].get("text","{}")
    try: return json.loads(text)
    except: return {"result": text}

def print_step(msg):
    print(f"  → {msg}", flush=True)

# ── Canvas layout ──────────────────────────────────────────────────────────────
# Single column, tight vertical spacing. Each component gets a fixed vertical
# slot. SECTION_STEP is the distance between section start points.
# Components use offsets of y+30 to y+240 from their start — fits in 280px each.

SECTION_STEP = 280   # vertical px between each section's starting y

def slot_pos(old_row):
    """Convert old row IDs (0, 2, 4 ... 32) to tightly-packed y positions."""
    section_index = old_row // 2
    return 40, 120 + section_index * SECTION_STEP

# ── Build the UI System ────────────────────────────────────────────────────────

def build():
    print("\n" + "="*60)
    print("  Mobility Global — UI System Builder")
    print("="*60 + "\n")

    # Check connection — figma-console-mcp returns {ok:true} not the JS return value,
    # so we check that the MCP server itself is reachable and relay is connected.
    try:
        health = mcp("tools/list", {})
        tool_count = len(health.get("result", {}).get("tools", []))
        if tool_count == 0:
            raise RuntimeError("No tools available")
        print(f"  MCP server connected — {tool_count} tools available")
    except Exception as e:
        print(f"ERROR: Cannot reach MCP server at {MCP_SERVER}: {e}")
        print("  Make sure FigmaMockupGenerator\\figma\\mcp\\server.py is running on port 7771")
        sys.exit(1)

    # Send a test notification to Figma so user can confirm plugin is active
    js("(async()=>{ figma.notify('UI System Builder connected!', {timeout:3000}); })();")
    print(f"  Figma Desktop Bridge connected — watch for notification in Figma\n")

    # ── Create UI System page ──────────────────────────────────────────────────
    print_step("Creating UI System page...")
    js("""
(async () => {
  var existing = figma.root.children.find(p => p.name === 'UI System');
  if (existing) { figma.currentPage = existing; }
  else {
    var p = figma.createPage();
    p.name = 'UI System';
    figma.currentPage = p;
  }
  figma.currentPage.backgrounds = [{type:'SOLID', color:{r:0.94,g:0.94,b:0.90}}];
  return JSON.stringify({ok:true});
})();
""")

    # ── Page title ────────────────────────────────────────────────────────────
    await_js("""
(async () => {
  await figma.loadFontAsync({family:'Inter',style:'Bold'});
  await figma.loadFontAsync({family:'Inter',style:'Regular'});
  await figma.loadFontAsync({family:'Inter',style:'Medium'});
  await figma.loadFontAsync({family:'Inter',style:'SemiBold'});

  var t = figma.createText();
  t.fontName = {family:'Inter',style:'Bold'};
  t.characters = 'Mobility Global — UI System';
  t.fontSize = 32;
  t.fills = [{type:'SOLID',color:{r:0.075,g:0.141,b:0.271}}]; // Vital Blue
  t.x = 40; t.y = 40;

  var sub = figma.createText();
  sub.fontName = {family:'Inter',style:'Regular'};
  sub.characters = 'Component library built on brand tokens  ·  v1.0';
  sub.fontSize = 14;
  sub.fills = [{type:'SOLID',color:{r:0.216,g:0.255,b:0.318}}];
  sub.x = 40; sub.y = 84;

  return JSON.stringify({ok:true});
})();
""")

    # Build all sections
    _color_palette()
    _typography()
    _buttons()
    _form_inputs()
    _dropdowns_and_selects()
    _tabs()
    _badges()
    _cards()
    _kpi_cards()
    _data_table()
    _alerts()
    _header()
    _sidebar()
    _footer()
    _modal()
    _breadcrumb()
    _pagination()
    _progress_bar()
    _avatar_and_avatar_group()
    _search_bar()
    _tooltip()

    print("\n" + "="*60)
    print("  UI System built successfully!")
    print("  Switch to the 'UI System' page in Figma to review.")
    print("="*60 + "\n")


def await_js(code):
    """Same as js() but makes the code readable."""
    return js(code)


def section_label(x, y, title):
    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'SemiBold'}});
  var t = figma.createText();
  t.fontName = {{family:'Inter',style:'SemiBold'}};
  t.characters = '{title}';
  t.fontSize = 18;
  t.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}];
  t.x = {x}; t.y = {y};
  return JSON.stringify({{ok:true}});
}})();
""")


# ── 1. Color Palette ──────────────────────────────────────────────────────────
def _color_palette():
    print_step("Color palette...")
    x, y = slot_pos(0)
    section_label(x, y, "Color Palette")
    colors = [
        ("#132445", "Vital Blue",       "Main Color"),
        ("#0064D2", "Forward Blue",     "Secondary"),
        ("#B8EAF5", "Morning Mist",     "Secondary"),
        ("#EFEFE5", "Quiet Light",      "Main Color"),
        ("#420E71", "Steady Lilac",     "Accent"),
        ("#E3ABFF", "Soft Lilac",       "Accent"),
        ("#FFE783", "Vital Spark",      "Accent"),
        ("#FDEBB3", "Clarity Yellow",   "Accent"),
        ("#059669", "Success",          "Semantic"),
        ("#DC2626", "Error",            "Semantic"),
        ("#D97706", "Warning",          "Semantic"),
        ("#FFFFFF", "White",            "Neutral"),
    ]
    col = 0
    for i, (hex_col, name, category) in enumerate(colors):
        cx = x + col * 100
        cy = y + 36 + (i // 12) * 140

        r2, g2, b2 = _hex_to_rgb(hex_col)
        border_r, border_g, border_b = _hex_to_rgb("#E5E7EB")
        text_col = "0.075,0.141,0.271" if hex_col not in ["#132445","#0064D2","#420E71"] else "1,1,1"

        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  await figma.loadFontAsync({{family:'Inter',style:'Bold'}});
  var swatch = figma.createFrame();
  swatch.resize(80, 80);
  swatch.cornerRadius = 8;
  swatch.fills = [{{type:'SOLID',color:{{r:{r2},g:{g2},b:{b2}}}}}];
  swatch.strokes = [{{type:'SOLID',color:{{r:{border_r},g:{border_g},b:{border_b}}}}}];
  swatch.strokeWeight = 1;
  swatch.x = {cx}; swatch.y = {cy};
  figma.currentPage.appendChild(swatch);

  var lbl = figma.createText();
  lbl.fontName = {{family:'Inter',style:'Bold'}};
  lbl.characters = '{name}';
  lbl.fontSize = 10;
  lbl.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}];
  lbl.x = {cx}; lbl.y = {cy + 86};
  figma.currentPage.appendChild(lbl);

  var hex_lbl = figma.createText();
  hex_lbl.fontName = {{family:'Inter',style:'Regular'}};
  hex_lbl.characters = '{hex_col}';
  hex_lbl.fontSize = 9;
  hex_lbl.fills = [{{type:'SOLID',color:{{r:0.38,g:0.44,b:0.52}}}}];
  hex_lbl.x = {cx}; hex_lbl.y = {cy + 100};
  figma.currentPage.appendChild(hex_lbl);

  return JSON.stringify({{ok:true}});
}})();
""")
        col += 1
        if col >= 12: col = 0


# ── 2. Typography ─────────────────────────────────────────────────────────────
def _typography():
    print_step("Typography scale...")
    x, y = slot_pos(2)
    section_label(x, y, "Typography")
    styles = [
        ("H1 — Page Title",    32, "Bold",     TEXT_PRIMARY),
        ("H2 — Section Title", 24, "SemiBold", TEXT_PRIMARY),
        ("H3 — Card Title",    20, "SemiBold", TEXT_PRIMARY),
        ("H4 — Subsection",    16, "SemiBold", TEXT_PRIMARY),
        ("Body Large",         16, "Regular",  TEXT_SECONDARY),
        ("Body",               14, "Regular",  TEXT_SECONDARY),
        ("Body Small",         13, "Regular",  TEXT_MUTED),
        ("Caption / Label",    11, "Medium",   TEXT_MUTED),
    ]
    for i, (label, size, weight, color) in enumerate(styles):
        r2, g2, b2 = _hex_to_rgb(color)
        ty = y + 36 + i * (size + 16)
        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'{weight}'}});
  var t = figma.createText();
  t.fontName = {{family:'Inter',style:'{weight}'}};
  t.characters = '{label}';
  t.fontSize = {size};
  t.fills = [{{type:'SOLID',color:{{r:{r2},g:{g2},b:{b2}}}}}];
  t.x = {x}; t.y = {ty};
  figma.currentPage.appendChild(t);
  return JSON.stringify({{ok:true}});
}})();
""")


# ── 3. Buttons ────────────────────────────────────────────────────────────────
def _buttons():
    print_step("Buttons...")
    x, y = slot_pos(4)
    section_label(x, y, "Buttons")

    buttons = [
        # label,       bg,           text,    border,        style
        ("Primary",      FORWARD_BLUE, WHITE,   FORWARD_BLUE, "filled"),
        ("Secondary",    WHITE,        FORWARD_BLUE, FORWARD_BLUE, "outline"),
        ("Ghost",        "transparent", FORWARD_BLUE, "transparent", "ghost"),
        ("Danger",       ERROR,        WHITE,   ERROR,        "filled"),
        ("Disabled",     "#E5E7EB",    TEXT_MUTED, "#E5E7EB",  "filled"),
        ("Success",      SUCCESS,      WHITE,   SUCCESS,      "filled"),
    ]
    for i, (label, bg, text_c, border, style) in enumerate(buttons):
        bx = x + i * 140
        by = y + 40
        r_bg, g_bg, b_bg = _hex_to_rgb(bg if bg != "transparent" else "#FFFFFF")
        r_t, g_t, b_t = _hex_to_rgb(text_c)
        r_br, g_br, b_br = _hex_to_rgb(border if border != "transparent" else "#E5E7EB")
        opacity = "0" if bg == "transparent" else "1"
        border_op = "0" if border == "transparent" else "1"

        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});
  var btn = figma.createFrame();
  btn.name = 'Button / {label}';
  btn.resize(120, 40);
  btn.cornerRadius = 8;
  btn.layoutMode = 'HORIZONTAL';
  btn.primaryAxisAlignItems = 'CENTER';
  btn.counterAxisAlignItems = 'CENTER';
  btn.primaryAxisSizingMode = 'FIXED';
  btn.counterAxisSizingMode = 'FIXED';
  btn.fills = [{opacity == "0" and "[]" or ""}{{type:'SOLID',color:{{r:{r_bg},g:{g_bg},b:{b_bg}}}}}].filter(Boolean);
  if ({opacity} === 0) btn.fills = [];
  btn.strokes = [{{type:'SOLID',color:{{r:{r_br},g:{g_br},b:{b_br}}}}}];
  btn.strokeWeight = {'0' if border == "transparent" else '1.5'};
  btn.effects = [{{"type":"DROP_SHADOW","color":{{"r":0,"g":0,"b":0,"a":0.08}},"offset":{{"x":0,"y":2}},"radius":4,"spread":0,"visible":true,"blendMode":"NORMAL"}}];
  btn.x = {bx}; btn.y = {by};
  figma.currentPage.appendChild(btn);

  var lbl = figma.createText();
  lbl.fontName = {{family:'Inter',style:'Medium'}};
  lbl.characters = '{label}';
  lbl.fontSize = 14;
  lbl.fills = [{{type:'SOLID',color:{{r:{r_t},g:{g_t},b:{b_t}}}}}];
  btn.appendChild(lbl);

  var caption = figma.createText();
  caption.fontName = {{family:'Inter',style:'Regular'}};
  caption.characters = '{label}';
  caption.fontSize = 11;
  caption.fills = [{{type:'SOLID',color:{{r:0.38,g:0.44,b:0.52}}}}];
  caption.x = {bx}; caption.y = {by + 50};
  figma.currentPage.appendChild(caption);

  return JSON.stringify({{ok:true}});
}})();
""")

    # Button sizes row
    sizes = [("Small", 32, 80, 12), ("Medium", 40, 120, 14), ("Large", 48, 144, 15)]
    for i, (sz_label, h, w, fs) in enumerate(sizes):
        bx = x + i * 160
        by = y + 130
        r_bg, g_bg, b_bg = _hex_to_rgb(FORWARD_BLUE)
        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});
  var btn = figma.createFrame();
  btn.name = 'Button / {sz_label}';
  btn.resize({w}, {h});
  btn.cornerRadius = 8;
  btn.layoutMode = 'HORIZONTAL';
  btn.primaryAxisAlignItems = 'CENTER';
  btn.counterAxisAlignItems = 'CENTER';
  btn.primaryAxisSizingMode = 'FIXED';
  btn.counterAxisSizingMode = 'FIXED';
  btn.fills = [{{type:'SOLID',color:{{r:{r_bg},g:{g_bg},b:{b_bg}}}}}];
  btn.x = {bx}; btn.y = {by};
  figma.currentPage.appendChild(btn);
  var lbl = figma.createText();
  lbl.fontName = {{family:'Inter',style:'Medium'}};
  lbl.characters = '{sz_label}';
  lbl.fontSize = {fs};
  lbl.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  btn.appendChild(lbl);
  return JSON.stringify({{ok:true}});
}})();
""")


# ── 4. Form Inputs ────────────────────────────────────────────────────────────
def _form_inputs():
    print_step("Form inputs...")
    x, y = slot_pos(6)
    section_label(x, y, "Form Inputs")

    fields = [
        ("Default",   "Email address",  BORDER,      WHITE,       TEXT_MUTED),
        ("Focused",   "user@company.com", FORWARD_BLUE, WHITE,    TEXT_PRIMARY),
        ("Filled",    "John Smith",     BORDER,      WHITE,       TEXT_PRIMARY),
        ("Error",     "Invalid email",  ERROR,       "#FEF2F2",   ERROR),
        ("Disabled",  "Not editable",   BORDER,      "#F9FAFB",   TEXT_MUTED),
    ]
    for i, (state, placeholder, border_c, bg_c, text_c) in enumerate(fields):
        fx = x + i * 220
        fy = y + 40
        r_b, g_b, b_b = _hex_to_rgb(border_c)
        r_bg, g_bg, b_bg = _hex_to_rgb(bg_c)
        r_t, g_t, b_t = _hex_to_rgb(text_c)
        shadow_a = "0.12" if state == "Focused" else "0.05"
        border_w = "2" if state == "Focused" else "1"

        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});

  // Label
  var lbl = figma.createText();
  lbl.fontName = {{family:'Inter',style:'Medium'}};
  lbl.characters = '{state}';
  lbl.fontSize = 12;
  lbl.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}];
  lbl.x = {fx}; lbl.y = {fy};
  figma.currentPage.appendChild(lbl);

  // Input container
  var inp = figma.createFrame();
  inp.name = 'Input / {state}';
  inp.resize(200, 40);
  inp.cornerRadius = 8;
  inp.fills = [{{type:'SOLID',color:{{r:{r_bg},g:{g_bg},b:{b_bg}}}}}];
  inp.strokes = [{{type:'SOLID',color:{{r:{r_b},g:{g_b},b:{b_b}}}}}];
  inp.strokeWeight = {border_w};
  inp.effects = [{{"type":"DROP_SHADOW","color":{{"r":0,"g":0,"b":0,"a":{shadow_a}}},"offset":{{"x":0,"y":2}},"radius":6,"spread":0,"visible":true,"blendMode":"NORMAL"}}];
  inp.x = {fx}; inp.y = {fy + 20};
  figma.currentPage.appendChild(inp);

  var placeholder = figma.createText();
  placeholder.fontName = {{family:'Inter',style:'Regular'}};
  placeholder.characters = '{placeholder}';
  placeholder.fontSize = 14;
  placeholder.fills = [{{type:'SOLID',color:{{r:{r_t},g:{g_t},b:{b_t}}}}}];
  placeholder.x = {fx + 12}; placeholder.y = {fy + 32};
  figma.currentPage.appendChild(placeholder);

  return JSON.stringify({{ok:true}});
}})();
""")

    # Textarea
    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  var r_b, g_b, b_b = {_hex_to_rgb(BORDER)};
  var ta = figma.createFrame();
  ta.name = 'Textarea';
  ta.resize(200, 100);
  ta.cornerRadius = 8;
  ta.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  ta.strokes = [{{type:'SOLID',color:{{r:0.898,g:0.906,b:0.918}}}}];
  ta.strokeWeight = 1;
  ta.x = {x}; ta.y = {y + 160};
  figma.currentPage.appendChild(ta);
  var lbl = figma.createText();
  lbl.fontName = {{family:'Inter',style:'Regular'}};
  lbl.characters = 'Type your message here...';
  lbl.fontSize = 14;
  lbl.fills = [{{type:'SOLID',color:{{r:0.612,g:0.639,b:0.675}}}}];
  lbl.x = {x + 12}; lbl.y = {y + 172};
  figma.currentPage.appendChild(lbl);
  return JSON.stringify({{ok:true}});
}})();
""")


# ── 5. Dropdowns ──────────────────────────────────────────────────────────────
def _dropdowns_and_selects():
    print_step("Dropdowns & selects...")
    x, y = slot_pos(8)
    section_label(x, y, "Dropdowns & Selects")

    # Closed dropdown
    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  var dd = figma.createFrame();
  dd.name = 'Dropdown / Closed';
  dd.resize(240, 40);
  dd.cornerRadius = 8;
  dd.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  dd.strokes = [{{type:'SOLID',color:{{r:0.898,g:0.906,b:0.918}}}}];
  dd.strokeWeight = 1;
  dd.x = {x}; dd.y = {y + 40};
  figma.currentPage.appendChild(dd);

  var lbl = figma.createText();
  lbl.fontName = {{family:'Inter',style:'Regular'}};
  lbl.characters = 'Select an option';
  lbl.fontSize = 14;
  lbl.fills = [{{type:'SOLID',color:{{r:0.612,g:0.639,b:0.675}}}}];
  lbl.x = {x + 12}; lbl.y = {y + 52};
  figma.currentPage.appendChild(lbl);

  // Chevron icon (simplified as triangle)
  var chevron = figma.createText();
  chevron.fontName = {{family:'Inter',style:'Regular'}};
  chevron.characters = '▾';
  chevron.fontSize = 14;
  chevron.fills = [{{type:'SOLID',color:{{r:0.38,g:0.44,b:0.52}}}}];
  chevron.x = {x + 212}; chevron.y = {y + 52};
  figma.currentPage.appendChild(chevron);

  return JSON.stringify({{ok:true}});
}})();
""")

    # Open dropdown with options
    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});

  var menu = figma.createFrame();
  menu.name = 'Dropdown / Open';
  menu.resize(240, 180);
  menu.cornerRadius = 8;
  menu.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  menu.strokes = [{{type:'SOLID',color:{{r:0.898,g:0.906,b:0.918}}}}];
  menu.strokeWeight = 1;
  menu.effects = [{{"type":"DROP_SHADOW","color":{{"r":0,"g":0,"b":0,"a":0.12}},"offset":{{"x":0,"y":4}},"radius":16,"spread":0,"visible":true,"blendMode":"NORMAL"}}];
  menu.x = {x + 280}; menu.y = {y + 40};
  figma.currentPage.appendChild(menu);

  var options = ['Option One', 'Option Two (Selected)', 'Option Three', 'Option Four'];
  for (var i = 0; i < options.length; i++) {{
    var row = figma.createFrame();
    row.resize(240, 40);
    row.x = 0; row.y = i * 40;
    if (i === 1) row.fills = [{{type:'SOLID',color:{{r:0.722,g:0.914,b:0.961}}}}]; // Morning Mist
    else row.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
    menu.appendChild(row);

    var t = figma.createText();
    t.fontName = i === 1 ? {{family:'Inter',style:'Medium'}} : {{family:'Inter',style:'Regular'}};
    t.characters = options[i];
    t.fontSize = 14;
    t.fills = i === 1
      ? [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}]
      : [{{type:'SOLID',color:{{r:0.216,g:0.255,b:0.318}}}}];
    t.x = 12; t.y = 12;
    row.appendChild(t);
  }}
  return JSON.stringify({{ok:true}});
}})();
""")


# ── 6. Tabs ───────────────────────────────────────────────────────────────────
def _tabs():
    print_step("Tabs...")
    x, y = slot_pos(10)
    section_label(x, y, "Tabs")

    tab_labels = ["Overview", "Analytics", "Reports", "Settings"]
    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});

  // Tab bar container
  var bar = figma.createFrame();
  bar.name = 'Tabs / Horizontal';
  bar.resize(560, 44);
  bar.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  bar.strokes = [{{type:'SOLID',color:{{r:0.898,g:0.906,b:0.918}}}}];
  bar.strokeWeight = 1;
  bar.layoutMode = 'HORIZONTAL';
  bar.primaryAxisAlignItems = 'MIN';
  bar.counterAxisAlignItems = 'CENTER';
  bar.primaryAxisSizingMode = 'FIXED';
  bar.counterAxisSizingMode = 'FIXED';
  bar.x = {x}; bar.y = {y + 40};
  figma.currentPage.appendChild(bar);

  var tab_names = {json.dumps(tab_labels)};
  for (var i = 0; i < tab_names.length; i++) {{
    var tab = figma.createFrame();
    tab.resize(140, 44);
    tab.layoutMode = 'HORIZONTAL';
    tab.primaryAxisAlignItems = 'CENTER';
    tab.counterAxisAlignItems = 'CENTER';
    tab.primaryAxisSizingMode = 'FIXED';
    tab.counterAxisSizingMode = 'FIXED';
    tab.fills = i === 0
      ? [{{type:'SOLID',color:{{r:0.722,g:0.914,b:0.961}}}}]  // Morning Mist active
      : [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];

    var t = figma.createText();
    t.fontName = i === 0 ? {{family:'Inter',style:'Medium'}} : {{family:'Inter',style:'Regular'}};
    t.characters = tab_names[i];
    t.fontSize = 14;
    t.fills = i === 0
      ? [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}]
      : [{{type:'SOLID',color:{{r:0.38,g:0.44,b:0.52}}}}];
    tab.appendChild(t);
    bar.appendChild(tab);

    // Active indicator bar
    if (i === 0) {{
      var indicator = figma.createRectangle();
      indicator.resize(140, 3);
      indicator.fills = [{{type:'SOLID',color:{{r:0,g:0.392,b:0.824}}}}]; // Forward Blue
      indicator.x = {x}; indicator.y = {y + 81};
      figma.currentPage.appendChild(indicator);
    }}
  }}

  // Vertical tabs
  var vbar = figma.createFrame();
  vbar.name = 'Tabs / Vertical';
  vbar.resize(180, 220);
  vbar.fills = [{{type:'SOLID',color:{{r:0.976,g:0.976,b:0.961}}}}];
  vbar.cornerRadius = 8;
  vbar.x = {x + 600}; vbar.y = {y + 40};
  figma.currentPage.appendChild(vbar);

  for (var j = 0; j < tab_names.length; j++) {{
    var vtab = figma.createFrame();
    vtab.resize(180, 48);
    vtab.y = j * 52 + 8;
    vtab.cornerRadius = 6;
    vtab.fills = j === 0
      ? [{{type:'SOLID',color:{{r:0.722,g:0.914,b:0.961}}}}]
      : [{{type:'SOLID',color:{{r:0,g:0,b:0,a:0}}}}];
    vtab.fills = j === 0
      ? [{{type:'SOLID',color:{{r:0.722,g:0.914,b:0.961}}}}]
      : [];

    var vt = figma.createText();
    vt.fontName = j === 0 ? {{family:'Inter',style:'Medium'}} : {{family:'Inter',style:'Regular'}};
    vt.characters = tab_names[j];
    vt.fontSize = 14;
    vt.fills = j === 0
      ? [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}]
      : [{{type:'SOLID',color:{{r:0.38,g:0.44,b:0.52}}}}];
    vt.x = 16; vt.y = 16;
    vtab.appendChild(vt);
    vbar.appendChild(vtab);
  }}

  return JSON.stringify({{ok:true}});
}})();
""")


# ── 7. Badges ─────────────────────────────────────────────────────────────────
def _badges():
    print_step("Badges & status pills...")
    x, y = slot_pos(12)
    section_label(x, y, "Badges & Status Pills")

    badges = [
        ("Active",    "#D1FAE5", SUCCESS,        "Active"),
        ("Inactive",  "#F3F4F6", TEXT_MUTED,     "Inactive"),
        ("Pending",   CLARITY_YEL, WARNING,      "Pending"),
        ("Error",     ERROR_BG,    ERROR,        "Error"),
        ("New",       MORNING_MIST, FORWARD_BLUE, "New"),
        ("Premium",   SOFT_LILAC,  STEADY_LILAC, "Premium"),
        ("Beta",      VITAL_SPARK, "#92400E",    "Beta"),
        ("1",         FORWARD_BLUE, WHITE,       "1"),
        ("24",        ERROR,       WHITE,        "24"),
        ("99+",       VITAL_BLUE,  WHITE,        "99+"),
    ]
    for i, (label, bg, text_c, display) in enumerate(badges):
        bx = x + (i % 5) * 120
        by = y + 40 + (i // 5) * 50
        r_bg, g_bg, b_bg = _hex_to_rgb(bg)
        r_t, g_t, b_t = _hex_to_rgb(text_c)
        is_dot = label in ["1","24","99+"]
        w = 32 if is_dot else max(60, len(display) * 8 + 24)

        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});
  var badge = figma.createFrame();
  badge.name = 'Badge / {label}';
  badge.resize({w}, 22);
  badge.cornerRadius = 999;
  badge.layoutMode = 'HORIZONTAL';
  badge.primaryAxisAlignItems = 'CENTER';
  badge.counterAxisAlignItems = 'CENTER';
  badge.primaryAxisSizingMode = 'FIXED';
  badge.counterAxisSizingMode = 'FIXED';
  badge.fills = [{{type:'SOLID',color:{{r:{r_bg},g:{g_bg},b:{b_bg}}}}}];
  badge.x = {bx}; badge.y = {by};
  figma.currentPage.appendChild(badge);

  var t = figma.createText();
  t.fontName = {{family:'Inter',style:'Medium'}};
  t.characters = '{display}';
  t.fontSize = {'11' if not is_dot else '10'};
  t.fills = [{{type:'SOLID',color:{{r:{r_t},g:{g_t},b:{b_t}}}}}];
  badge.appendChild(t);
  return JSON.stringify({{ok:true}});
}})();
""")


# ── 8. Cards ──────────────────────────────────────────────────────────────────
def _cards():
    print_step("Cards...")
    x, y = slot_pos(14)
    section_label(x, y, "Cards")

    card_types = [
        ("Basic Card",     FORWARD_BLUE),
        ("Info Card",      STEADY_LILAC),
        ("Warning Card",   WARNING),
        ("Success Card",   SUCCESS),
    ]
    for i, (card_label, accent) in enumerate(card_types):
        cx = x + i * 220
        cy = y + 40
        r_a, g_a, b_a = _hex_to_rgb(accent)

        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Bold'}});
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});

  var card = figma.createFrame();
  card.name = '{card_label}';
  card.resize(200, 160);
  card.cornerRadius = 12;
  card.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  card.effects = [{{"type":"DROP_SHADOW","color":{{"r":0,"g":0,"b":0,"a":0.08}},"offset":{{"x":0,"y":4}},"radius":12,"spread":0,"visible":true,"blendMode":"NORMAL"}}];
  card.x = {cx}; card.y = {cy};
  figma.currentPage.appendChild(card);

  // Top accent stripe
  var stripe = figma.createRectangle();
  stripe.resize(200, 4);
  stripe.fills = [{{type:'SOLID',color:{{r:{r_a},g:{g_a},b:{b_a}}}}}];
  stripe.cornerRadius = 12;
  stripe.y = 0;
  card.appendChild(stripe);

  var title = figma.createText();
  title.fontName = {{family:'Inter',style:'Bold'}};
  title.characters = '{card_label}';
  title.fontSize = 15;
  title.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}];
  title.x = 16; title.y = 20;
  card.appendChild(title);

  var body = figma.createText();
  body.fontName = {{family:'Inter',style:'Regular'}};
  body.characters = 'Card body text goes here. Use for any content block.';
  body.fontSize = 13;
  body.fills = [{{type:'SOLID',color:{{r:0.216,g:0.255,b:0.318}}}}];
  body.textAutoResize = 'WIDTH_AND_HEIGHT';
  body.x = 16; body.y = 50;
  card.appendChild(body);

  return JSON.stringify({{ok:true}});
}})();
""")


# ── 9. KPI Cards ──────────────────────────────────────────────────────────────
def _kpi_cards():
    print_step("KPI cards...")
    x, y = slot_pos(16)
    section_label(x, y, "KPI Cards")

    kpis = [
        ("Total Revenue",  "$4.2M",  "+12.3%", True,  FORWARD_BLUE),
        ("Active Users",   "28,450", "+8.7%",  True,  SUCCESS),
        ("Avg. Rating",    "4.8",    "-0.2",   False, ERROR),
        ("Transactions",   "1,284",  "+24.1%", True,  STEADY_LILAC),
    ]
    for i, (label, value, change, is_up, color) in enumerate(kpis):
        kx = x + i * 200
        ky = y + 40
        r_c, g_c, b_c = _hex_to_rgb(color)
        change_color = SUCCESS if is_up else ERROR
        r_ch, g_ch, b_ch = _hex_to_rgb(change_color)

        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Bold'}});
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});

  var card = figma.createFrame();
  card.name = 'KPI / {label}';
  card.resize(180, 120);
  card.cornerRadius = 12;
  card.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  card.effects = [{{"type":"DROP_SHADOW","color":{{"r":0,"g":0,"b":0,"a":0.07}},"offset":{{"x":0,"y":4}},"radius":12,"spread":0,"visible":true,"blendMode":"NORMAL"}}];
  card.x = {kx}; card.y = {ky};
  figma.currentPage.appendChild(card);

  // Color dot
  var dot = figma.createEllipse();
  dot.resize(8, 8);
  dot.fills = [{{type:'SOLID',color:{{r:{r_c},g:{g_c},b:{b_c}}}}}];
  dot.x = 16; dot.y = 18;
  card.appendChild(dot);

  var label_t = figma.createText();
  label_t.fontName = {{family:'Inter',style:'Regular'}};
  label_t.characters = '{label}';
  label_t.fontSize = 12;
  label_t.fills = [{{type:'SOLID',color:{{r:0.38,g:0.44,b:0.52}}}}];
  label_t.x = 30; label_t.y = 14;
  card.appendChild(label_t);

  var value_t = figma.createText();
  value_t.fontName = {{family:'Inter',style:'Bold'}};
  value_t.characters = '{value}';
  value_t.fontSize = 28;
  value_t.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}];
  value_t.x = 16; value_t.y = 40;
  card.appendChild(value_t);

  var change_t = figma.createText();
  change_t.fontName = {{family:'Inter',style:'Medium'}};
  change_t.characters = '{'↑' if is_up else '↓'} {change} vs last month';
  change_t.fontSize = 11;
  change_t.fills = [{{type:'SOLID',color:{{r:{r_ch},g:{g_ch},b:{b_ch}}}}}];
  change_t.x = 16; change_t.y = 88;
  card.appendChild(change_t);

  return JSON.stringify({{ok:true}});
}})();
""")


# ── 10. Data Table ────────────────────────────────────────────────────────────
def _data_table():
    print_step("Data table...")
    x, y = slot_pos(18)
    section_label(x, y, "Data Table")

    cols = ["Name", "Role", "Department", "Status", "Actions"]
    col_widths = [160, 120, 140, 100, 100]
    rows = [
        ["Sarah Johnson",  "Director",  "Product",     "Active",   "Edit  ···"],
        ["Michael Chen",   "Manager",   "Engineering", "Active",   "Edit  ···"],
        ["Emma Wilson",    "Analyst",   "Finance",     "Pending",  "Edit  ···"],
        ["James Torres",   "Lead",      "Marketing",   "Inactive", "Edit  ···"],
    ]

    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Bold'}});
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});

  var cols = {json.dumps(cols)};
  var col_widths = {json.dumps(col_widths)};
  var rows = {json.dumps(rows)};
  var status_colors = {{
    'Active':   {{bg:[0.820,0.976,0.914], text:[0.035,0.588,0.416]}},
    'Pending':  {{bg:[0.992,0.929,0.702], text:[0.855,0.467,0.035]}},
    'Inactive': {{bg:[0.957,0.957,0.957], text:[0.38,0.44,0.52]}},
  }};

  var total_w = col_widths.reduce((a,b)=>a+b, 0);
  var table = figma.createFrame();
  table.name = 'Data Table';
  table.resize(total_w, (rows.length + 1) * 48);
  table.cornerRadius = 12;
  table.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  table.effects = [{{"type":"DROP_SHADOW","color":{{"r":0,"g":0,"b":0,"a":0.07}},"offset":{{"x":0,"y":4}},"radius":12,"spread":0,"visible":true,"blendMode":"NORMAL"}}];
  table.strokes = [{{type:'SOLID',color:{{r:0.898,g:0.906,b:0.918}}}}];
  table.strokeWeight = 1;
  table.x = {x}; table.y = {y + 40};
  figma.currentPage.appendChild(table);

  // Header row
  var cx = 0;
  for (var c = 0; c < cols.length; c++) {{
    var hcell = figma.createFrame();
    hcell.resize(col_widths[c], 48);
    hcell.x = cx; hcell.y = 0;
    hcell.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}]; // Vital Blue header
    table.appendChild(hcell);

    var ht = figma.createText();
    ht.fontName = {{family:'Inter',style:'Bold'}};
    ht.characters = cols[c];
    ht.fontSize = 13;
    ht.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
    ht.x = 16; ht.y = 16;
    hcell.appendChild(ht);
    cx += col_widths[c];
  }}

  // Data rows
  for (var r = 0; r < rows.length; r++) {{
    cx = 0;
    var row_bg = r % 2 === 0
      ? {{r:1,g:1,b:1}}
      : {{r:0.976,g:0.980,b:0.988}};

    for (var c2 = 0; c2 < cols.length; c2++) {{
      var cell = figma.createFrame();
      cell.resize(col_widths[c2], 48);
      cell.x = cx; cell.y = (r + 1) * 48;
      cell.fills = [{{type:'SOLID',color:row_bg}}];
      cell.strokes = [{{type:'SOLID',color:{{r:0.937,g:0.941,b:0.949}}}}];
      cell.strokeWeight = 1;
      table.appendChild(cell);

      var cell_text = rows[r][c2];
      if (cols[c2] === 'Status') {{
        var sc = status_colors[cell_text] || status_colors['Inactive'];
        var sbadge = figma.createFrame();
        sbadge.resize(70, 22);
        sbadge.cornerRadius = 999;
        sbadge.fills = [{{type:'SOLID',color:{{r:sc.bg[0],g:sc.bg[1],b:sc.bg[2]}}}}];
        sbadge.x = 8; sbadge.y = 13;
        cell.appendChild(sbadge);
        var st = figma.createText();
        st.fontName = {{family:'Inter',style:'Medium'}};
        st.characters = cell_text;
        st.fontSize = 11;
        st.fills = [{{type:'SOLID',color:{{r:sc.text[0],g:sc.text[1],b:sc.text[2]}}}}];
        st.x = 10; st.y = 5;
        sbadge.appendChild(st);
      }} else {{
        var dt = figma.createText();
        dt.fontName = {{family:'Inter',style:c2 === 0 ? 'Medium' : 'Regular'}};
        dt.characters = cell_text;
        dt.fontSize = 13;
        dt.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}];
        dt.x = 16; dt.y = 16;
        cell.appendChild(dt);
      }}
      cx += col_widths[c2];
    }}
  }}

  return JSON.stringify({{ok:true}});
}})();
""")


# ── 11. Alert Banners ─────────────────────────────────────────────────────────
def _alerts():
    print_step("Alert banners...")
    x, y = slot_pos(20)
    section_label(x, y, "Alert Banners")

    alerts = [
        ("Info",    MORNING_MIST, FORWARD_BLUE, "ℹ", "Information: This is an informational message."),
        ("Success", SUCCESS_BG,   SUCCESS,      "✓", "Success: Your changes have been saved."),
        ("Warning", CLARITY_YEL,  WARNING,      "⚠", "Warning: Please review before continuing."),
        ("Error",   ERROR_BG,     ERROR,        "✕", "Error: Something went wrong. Please try again."),
    ]
    for i, (label, bg, icon_c, icon, message) in enumerate(alerts):
        ax = x
        ay = y + 40 + i * 64
        r_bg, g_bg, b_bg = _hex_to_rgb(bg)
        r_ic, g_ic, b_ic = _hex_to_rgb(icon_c)

        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});

  var banner = figma.createFrame();
  banner.name = 'Alert / {label}';
  banner.resize(560, 48);
  banner.cornerRadius = 8;
  banner.fills = [{{type:'SOLID',color:{{r:{r_bg},g:{g_bg},b:{b_bg}}}}}];
  banner.strokes = [{{type:'SOLID',color:{{r:{r_ic},g:{g_ic},b:{b_ic}}}}}];
  banner.strokeWeight = 1;
  banner.x = {ax}; banner.y = {ay};
  figma.currentPage.appendChild(banner);

  var icon_t = figma.createText();
  icon_t.fontName = {{family:'Inter',style:'Medium'}};
  icon_t.characters = '{icon}';
  icon_t.fontSize = 14;
  icon_t.fills = [{{type:'SOLID',color:{{r:{r_ic},g:{g_ic},b:{b_ic}}}}}];
  icon_t.x = 16; icon_t.y = 16;
  banner.appendChild(icon_t);

  var msg = figma.createText();
  msg.fontName = {{family:'Inter',style:'Regular'}};
  msg.characters = '{message}';
  msg.fontSize = 14;
  msg.fills = [{{type:'SOLID',color:{{r:{r_ic},g:{g_ic},b:{b_ic}}}}}];
  msg.x = 40; msg.y = 16;
  banner.appendChild(msg);

  return JSON.stringify({{ok:true}});
}})();
""")


# ── 12. Header ────────────────────────────────────────────────────────────────
def _header():
    print_step("Header component...")
    x, y = slot_pos(22)
    section_label(x, y, "Header")

    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Bold'}});
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});

  var header = figma.createFrame();
  header.name = 'Header / Desktop';
  header.resize(1200, 64);
  header.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  header.strokes = [{{type:'SOLID',color:{{r:0.898,g:0.906,b:0.918}}}}];
  header.strokeWeight = 1;
  header.effects = [{{"type":"DROP_SHADOW","color":{{"r":0,"g":0,"b":0,"a":0.06}},"offset":{{"x":0,"y":2}},"radius":8,"spread":0,"visible":true,"blendMode":"NORMAL"}}];
  header.x = {x}; header.y = {y + 40};
  figma.currentPage.appendChild(header);

  // Logo area (white bg as specified)
  var logo_area = figma.createFrame();
  logo_area.resize(200, 64);
  logo_area.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  logo_area.x = 0; logo_area.y = 0;
  header.appendChild(logo_area);

  var logo_text = figma.createText();
  logo_text.fontName = {{family:'Inter',style:'Bold'}};
  logo_text.characters = 'Mobility Global';
  logo_text.fontSize = 16;
  logo_text.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}];
  logo_text.x = 16; logo_text.y = 22;
  logo_area.appendChild(logo_text);

  // Nav links
  var nav_items = ['Dashboard', 'Analytics', 'Reports', 'Settings'];
  for (var i = 0; i < nav_items.length; i++) {{
    var nav_t = figma.createText();
    nav_t.fontName = i === 0 ? {{family:'Inter',style:'Medium'}} : {{family:'Inter',style:'Regular'}};
    nav_t.characters = nav_items[i];
    nav_t.fontSize = 14;
    nav_t.fills = i === 0
      ? [{{type:'SOLID',color:{{r:0,g:0.392,b:0.824}}}}]  // Forward Blue active
      : [{{type:'SOLID',color:{{r:0.216,g:0.255,b:0.318}}}}];
    nav_t.x = 220 + i * 110; nav_t.y = 24;
    header.appendChild(nav_t);
  }}

  // Active underline
  var underline = figma.createRectangle();
  underline.resize(70, 2);
  underline.fills = [{{type:'SOLID',color:{{r:0,g:0.392,b:0.824}}}}];
  underline.x = 220; underline.y = 62;
  header.appendChild(underline);

  // Right side — search + avatar
  var search_box = figma.createFrame();
  search_box.resize(200, 36);
  search_box.cornerRadius = 8;
  search_box.fills = [{{type:'SOLID',color:{{r:0.976,g:0.976,b:0.961}}}}]; // Quiet Light
  search_box.strokes = [{{type:'SOLID',color:{{r:0.898,g:0.906,b:0.918}}}}];
  search_box.strokeWeight = 1;
  search_box.x = 880; search_box.y = 14;
  header.appendChild(search_box);

  var search_t = figma.createText();
  search_t.fontName = {{family:'Inter',style:'Regular'}};
  search_t.characters = '🔍  Search...';
  search_t.fontSize = 13;
  search_t.fills = [{{type:'SOLID',color:{{r:0.612,g:0.639,b:0.675}}}}];
  search_t.x = 10; search_t.y = 10;
  search_box.appendChild(search_t);

  // Bell icon
  var bell = figma.createText();
  bell.fontName = {{family:'Inter',style:'Regular'}};
  bell.characters = '🔔';
  bell.fontSize = 18;
  bell.x = 1100; bell.y = 22;
  header.appendChild(bell);

  // Avatar
  var avatar = figma.createEllipse();
  avatar.resize(36, 36);
  avatar.fills = [{{type:'SOLID',color:{{r:0,g:0.392,b:0.824}}}}]; // Forward Blue
  avatar.x = 1140; avatar.y = 14;
  header.appendChild(avatar);

  var av_t = figma.createText();
  av_t.fontName = {{family:'Inter',style:'Bold'}};
  av_t.characters = 'SG';
  av_t.fontSize = 12;
  av_t.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  av_t.x = 1150; av_t.y = 25;
  header.appendChild(av_t);

  return JSON.stringify({{ok:true}});
}})();
""")


# ── 13. Sidebar ───────────────────────────────────────────────────────────────
def _sidebar():
    print_step("Sidebar navigation...")
    x, y = slot_pos(24)
    section_label(x, y, "Sidebar Navigation")

    nav_items = [
        ("🏠", "Dashboard",   True),
        ("📊", "Analytics",   False),
        ("📋", "Reports",     False),
        ("👥", "Users",       False),
        ("⚙️", "Settings",    False),
    ]

    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  await figma.loadFontAsync({{family:'Inter',style:'Bold'}});

  var sidebar = figma.createFrame();
  sidebar.name = 'Sidebar / Navigation';
  sidebar.resize(240, 500);
  sidebar.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}]; // Vital Blue
  sidebar.x = {x}; sidebar.y = {y + 40};
  figma.currentPage.appendChild(sidebar);

  // Logo area
  var logo = figma.createFrame();
  logo.resize(240, 64);
  logo.fills = [{{type:'SOLID',color:{{r:0.047,g:0.094,b:0.180}}}}]; // Slightly darker
  logo.x = 0; logo.y = 0;
  sidebar.appendChild(logo);

  var logo_t = figma.createText();
  logo_t.fontName = {{family:'Inter',style:'Bold'}};
  logo_t.characters = 'Mobility Global';
  logo_t.fontSize = 15;
  logo_t.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  logo_t.x = 16; logo_t.y = 22;
  logo.appendChild(logo_t);

  var nav_items = {json.dumps(nav_items)};
  for (var i = 0; i < nav_items.length; i++) {{
    var item = nav_items[i];
    var nav_row = figma.createFrame();
    nav_row.resize(240, 48);
    nav_row.x = 0; nav_row.y = 80 + i * 52;
    nav_row.cornerRadius = i === 0 ? 0 : 0;

    if (item[2]) {{
      // Active item
      nav_row.fills = [{{type:'SOLID',color:{{r:0,g:0.392,b:0.824}}}}]; // Forward Blue
      // Active indicator bar
      var bar = figma.createRectangle();
      bar.resize(4, 48);
      bar.fills = [{{type:'SOLID',color:{{r:0.722,g:0.914,b:0.961}}}}]; // Morning Mist
      bar.x = 0; bar.y = 0;
      nav_row.appendChild(bar);
    }} else {{
      nav_row.fills = [];
    }}
    sidebar.appendChild(nav_row);

    var icon_t = figma.createText();
    icon_t.fontName = {{family:'Inter',style:'Regular'}};
    icon_t.characters = item[0];
    icon_t.fontSize = 16;
    icon_t.x = 16; icon_t.y = 14;
    nav_row.appendChild(icon_t);

    var nav_t = figma.createText();
    nav_t.fontName = item[2] ? {{family:'Inter',style:'Medium'}} : {{family:'Inter',style:'Regular'}};
    nav_t.characters = item[1];
    nav_t.fontSize = 14;
    nav_t.fills = [{{type:'SOLID',color:item[2] ? {{r:1,g:1,b:1}} : {{r:0.722,g:0.914,b:0.961,a:0.7}}}}];
    nav_t.x = 44; nav_t.y = 16;
    nav_row.appendChild(nav_t);
  }}

  // Bottom user section
  var user_area = figma.createFrame();
  user_area.resize(240, 64);
  user_area.fills = [{{type:'SOLID',color:{{r:0.047,g:0.094,b:0.180}}}}];
  user_area.x = 0; user_area.y = 436;
  sidebar.appendChild(user_area);

  var av = figma.createEllipse();
  av.resize(32, 32);
  av.fills = [{{type:'SOLID',color:{{r:0,g:0.392,b:0.824}}}}];
  av.x = 12; av.y = 16;
  user_area.appendChild(av);

  var user_t = figma.createText();
  user_t.fontName = {{family:'Inter',style:'Medium'}};
  user_t.characters = 'Srikanth C.';
  user_t.fontSize = 13;
  user_t.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  user_t.x = 52; user_t.y = 18;
  user_area.appendChild(user_t);

  var role_t = figma.createText();
  role_t.fontName = {{family:'Inter',style:'Regular'}};
  role_t.characters = 'Admin';
  role_t.fontSize = 11;
  role_t.fills = [{{type:'SOLID',color:{{r:0.722,g:0.914,b:0.961,a:0.7}}}}];
  role_t.x = 52; role_t.y = 34;
  user_area.appendChild(role_t);

  return JSON.stringify({{ok:true}});
}})();
""")


# ── 14. Footer ────────────────────────────────────────────────────────────────
def _footer():
    print_step("Footer...")
    x, y = slot_pos(26)
    section_label(x, y, "Footer")

    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});

  var footer = figma.createFrame();
  footer.name = 'Footer / Desktop';
  footer.resize(1200, 56);
  footer.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}]; // Vital Blue
  footer.x = {x}; footer.y = {y + 40};
  figma.currentPage.appendChild(footer);

  var copy = figma.createText();
  copy.fontName = {{family:'Inter',style:'Regular'}};
  copy.characters = '© 2025 Mobility Global. All rights reserved.';
  copy.fontSize = 12;
  copy.fills = [{{type:'SOLID',color:{{r:0.722,g:0.914,b:0.961}}}}]; // Morning Mist
  copy.x = 24; copy.y = 20;
  footer.appendChild(copy);

  var links = ['Privacy Policy', 'Terms of Use', 'Contact', 'Help Center'];
  for (var i = 0; i < links.length; i++) {{
    var lnk = figma.createText();
    lnk.fontName = {{family:'Inter',style:'Regular'}};
    lnk.characters = links[i];
    lnk.fontSize = 12;
    lnk.fills = [{{type:'SOLID',color:{{r:0.722,g:0.914,b:0.961}}}}];
    lnk.x = 800 + i * 110; lnk.y = 20;
    footer.appendChild(lnk);
  }}

  return JSON.stringify({{ok:true}});
}})();
""")


# ── 15. Modal ─────────────────────────────────────────────────────────────────
def _modal():
    print_step("Modal dialog...")
    x, y = slot_pos(28)
    section_label(x, y, "Modal Dialog")

    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Bold'}});
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});

  // Overlay scrim
  var scrim = figma.createRectangle();
  scrim.resize(560, 360);
  scrim.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271,a:0.4}}}}];
  scrim.cornerRadius = 4;
  scrim.x = {x}; scrim.y = {y + 40};
  figma.currentPage.appendChild(scrim);

  // Modal card
  var modal = figma.createFrame();
  modal.name = 'Modal / Confirm';
  modal.resize(400, 240);
  modal.cornerRadius = 16;
  modal.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  modal.effects = [{{"type":"DROP_SHADOW","color":{{"r":0,"g":0,"b":0,"a":0.25}},"offset":{{"x":0,"y":16}},"radius":40,"spread":0,"visible":true,"blendMode":"NORMAL"}}];
  modal.x = {x + 80}; modal.y = {y + 100};
  figma.currentPage.appendChild(modal);

  // Header stripe
  var mheader = figma.createFrame();
  mheader.resize(400, 56);
  mheader.fills = [{{type:'SOLID',color:{{r:0.076,g:0.141,b:0.271}}}}]; // Vital Blue
  mheader.cornerRadius = 16;
  mheader.x = 0; mheader.y = 0;
  modal.appendChild(mheader);

  var mtitle = figma.createText();
  mtitle.fontName = {{family:'Inter',style:'Bold'}};
  mtitle.characters = 'Confirm Action';
  mtitle.fontSize = 16;
  mtitle.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  mtitle.x = 24; mtitle.y = 18;
  mheader.appendChild(mtitle);

  var close = figma.createText();
  close.fontName = {{family:'Inter',style:'Regular'}};
  close.characters = '✕';
  close.fontSize = 14;
  close.fills = [{{type:'SOLID',color:{{r:0.722,g:0.914,b:0.961}}}}];
  close.x = 368; close.y = 20;
  mheader.appendChild(close);

  var mbody = figma.createText();
  mbody.fontName = {{family:'Inter',style:'Regular'}};
  mbody.characters = 'Are you sure you want to proceed? This action cannot be undone.';
  mbody.fontSize = 14;
  mbody.fills = [{{type:'SOLID',color:{{r:0.216,g:0.255,b:0.318}}}}];
  mbody.textAutoResize = 'WIDTH_AND_HEIGHT';
  mbody.resize(352, 50);
  mbody.x = 24; mbody.y = 72;
  modal.appendChild(mbody);

  // Buttons
  var cancel = figma.createFrame();
  cancel.resize(120, 40);
  cancel.cornerRadius = 8;
  cancel.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  cancel.strokes = [{{type:'SOLID',color:{{r:0.898,g:0.906,b:0.918}}}}];
  cancel.strokeWeight = 1.5;
  cancel.x = 148; cancel.y = 184;
  modal.appendChild(cancel);

  var ct = figma.createText();
  ct.fontName = {{family:'Inter',style:'Medium'}};
  ct.characters = 'Cancel';
  ct.fontSize = 14;
  ct.fills = [{{type:'SOLID',color:{{r:0.216,g:0.255,b:0.318}}}}];
  ct.x = 38; ct.y = 12;
  cancel.appendChild(ct);

  var confirm = figma.createFrame();
  confirm.resize(120, 40);
  confirm.cornerRadius = 8;
  confirm.fills = [{{type:'SOLID',color:{{r:0,g:0.392,b:0.824}}}}]; // Forward Blue
  confirm.x = 280; confirm.y = 184;
  modal.appendChild(confirm);

  var conf_t = figma.createText();
  conf_t.fontName = {{family:'Inter',style:'Medium'}};
  conf_t.characters = 'Confirm';
  conf_t.fontSize = 14;
  conf_t.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  conf_t.x = 32; conf_t.y = 12;
  confirm.appendChild(conf_t);

  return JSON.stringify({{ok:true}});
}})();
""")


# ── 16. Misc: Breadcrumb, Pagination, Progress, Tooltip, Avatar, Search ───────
def _breadcrumb():
    print_step("Breadcrumb...")
    x, y = slot_pos(30)
    section_label(x, y, "Breadcrumb / Pagination / Progress")
    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  await figma.loadFontAsync({{family:'Inter',style:'Medium'}});
  var parts = ['Home', '›', 'Analytics', '›', 'Reports', '›', 'Q4 2024'];
  var colors = [
    {{r:0,g:0.392,b:0.824}},
    {{r:0.612,g:0.639,b:0.675}},
    {{r:0,g:0.392,b:0.824}},
    {{r:0.612,g:0.639,b:0.675}},
    {{r:0,g:0.392,b:0.824}},
    {{r:0.612,g:0.639,b:0.675}},
    {{r:0.075,g:0.141,b:0.271}},
  ];
  var cx = {x};
  for (var i = 0; i < parts.length; i++) {{
    var t = figma.createText();
    t.fontName = i === 6 ? {{family:'Inter',style:'Medium'}} : {{family:'Inter',style:'Regular'}};
    t.characters = parts[i];
    t.fontSize = 13;
    t.fills = [{{type:'SOLID',color:colors[i]}}];
    t.x = cx; t.y = {y + 40};
    figma.currentPage.appendChild(t);
    cx += parts[i].length * 7 + 6;
  }}
  return JSON.stringify({{ok:true}});
}})();
""")


def _pagination():
    x, y_base = slot_pos(30)
    pages = ["«", "1", "2", "3", "...", "8", "9", "»"]
    active = "3"
    px = x
    for p in pages:
        is_active = p == active
        r_bg = "0,0.392,0.824" if is_active else "1,1,1"
        r_t  = "1,1,1" if is_active else "0.216,0.255,0.318"
        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'{('Medium' if '{p}' == '{active}' else 'Regular')}'}});
  var pg = figma.createFrame();
  pg.resize(36, 36);
  pg.cornerRadius = 8;
  pg.fills = [{{type:'SOLID',color:{{r:{r_bg.split(',')[0]},g:{r_bg.split(',')[1]},b:{r_bg.split(',')[2]}}}}}];
  pg.strokes = [{{type:'SOLID',color:{{r:0.898,g:0.906,b:0.918}}}}];
  pg.strokeWeight = 1;
  pg.layoutMode = 'HORIZONTAL';
  pg.primaryAxisAlignItems = 'CENTER';
  pg.counterAxisAlignItems = 'CENTER';
  pg.primaryAxisSizingMode = 'FIXED';
  pg.counterAxisSizingMode = 'FIXED';
  pg.x = {px}; pg.y = {y_base + 80};
  figma.currentPage.appendChild(pg);
  var t = figma.createText();
  t.fontName = {{family:'Inter',style:'{'Medium' if p == active else 'Regular'}'}};
  t.characters = '{p}';
  t.fontSize = 13;
  t.fills = [{{type:'SOLID',color:{{r:{r_t.split(',')[0]},g:{r_t.split(',')[1]},b:{r_t.split(',')[2]}}}}}];
  pg.appendChild(t);
  return JSON.stringify({{ok:true}});
}})();
""")
        px += 44


def _progress_bar():
    x, y_base = slot_pos(30)
    bars = [(65, FORWARD_BLUE, "65% Complete"), (100, SUCCESS, "Complete"), (30, WARNING, "30% In Progress")]
    for i, (pct, color, label) in enumerate(bars):
        r_c, g_c, b_c = _hex_to_rgb(color)
        bx, by = x + i * 280, y_base + 130
        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  var track = figma.createFrame();
  track.name = 'Progress / {label}';
  track.resize(240, 8);
  track.cornerRadius = 999;
  track.fills = [{{type:'SOLID',color:{{r:0.898,g:0.906,b:0.918}}}}];
  track.x = {bx}; track.y = {by};
  figma.currentPage.appendChild(track);
  var fill = figma.createFrame();
  fill.resize({int(240 * pct / 100)}, 8);
  fill.cornerRadius = 999;
  fill.fills = [{{type:'SOLID',color:{{r:{r_c},g:{g_c},b:{b_c}}}}}];
  fill.x = 0; fill.y = 0;
  track.appendChild(fill);
  var lbl = figma.createText();
  lbl.fontName = {{family:'Inter',style:'Regular'}};
  lbl.characters = '{label}';
  lbl.fontSize = 11;
  lbl.fills = [{{type:'SOLID',color:{{r:0.38,g:0.44,b:0.52}}}}];
  lbl.x = {bx}; lbl.y = {by + 14};
  figma.currentPage.appendChild(lbl);
  return JSON.stringify({{ok:true}});
}})();
""")


def _avatar_and_avatar_group():
    print_step("Avatars...")
    x, y = slot_pos(32)
    section_label(x, y, "Avatars & Search Bar")
    sizes = [(48, 15, "LG"), (36, 12, "MD"), (28, 10, "SM"), (20, 8, "XS")]
    initials = ["SG", "JC", "EM", "AT"]
    av_colors = [FORWARD_BLUE, STEADY_LILAC, SUCCESS, WARNING]
    for i, ((sz, fs, sz_label), init, col) in enumerate(zip(sizes, initials, av_colors)):
        ax = x + i * 80
        ay = y + 40
        r_c, g_c, b_c = _hex_to_rgb(col)
        await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Bold'}});
  var av = figma.createEllipse();
  av.resize({sz}, {sz});
  av.fills = [{{type:'SOLID',color:{{r:{r_c},g:{g_c},b:{b_c}}}}}];
  av.x = {ax}; av.y = {ay};
  figma.currentPage.appendChild(av);
  var t = figma.createText();
  t.fontName = {{family:'Inter',style:'Bold'}};
  t.characters = '{init}';
  t.fontSize = {fs};
  t.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  t.x = {ax + sz//2 - fs//2 - 2}; t.y = {ay + sz//2 - fs//2 - 1};
  figma.currentPage.appendChild(t);
  return JSON.stringify({{ok:true}});
}})();
""")


def _search_bar():
    x, y = slot_pos(32)
    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  var search = figma.createFrame();
  search.name = 'Search Bar';
  search.resize(320, 44);
  search.cornerRadius = 22;
  search.fills = [{{type:'SOLID',color:{{r:0.976,g:0.976,b:0.961}}}}];
  search.strokes = [{{type:'SOLID',color:{{r:0,g:0.392,b:0.824}}}}];
  search.strokeWeight = 1.5;
  search.effects = [{{"type":"DROP_SHADOW","color":{{"r":0,"g":0.392,"b":0.824,"a":0.15}},"offset":{{"x":0,"y":2}},"radius":8,"spread":0,"visible":true,"blendMode":"NORMAL"}}];
  search.x = {x + 400}; search.y = {y + 40};
  figma.currentPage.appendChild(search);
  var t = figma.createText();
  t.fontName = {{family:'Inter',style:'Regular'}};
  t.characters = '🔍  Search across all records...';
  t.fontSize = 14;
  t.fills = [{{type:'SOLID',color:{{r:0.612,g:0.639,b:0.675}}}}];
  t.x = 16; t.y = 14;
  search.appendChild(t);
  return JSON.stringify({{ok:true}});
}})();
""")


def _tooltip():
    print_step("Tooltip...")
    x, y = slot_pos(32)
    await_js(f"""
(async () => {{
  await figma.loadFontAsync({{family:'Inter',style:'Regular'}});
  var tt = figma.createFrame();
  tt.name = 'Tooltip';
  tt.resize(200, 36);
  tt.cornerRadius = 6;
  tt.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}];
  tt.effects = [{{"type":"DROP_SHADOW","color":{{"r":0,"g":0,"b":0,"a":0.2}},"offset":{{"x":0,"y":4}},"radius":8,"spread":0,"visible":true,"blendMode":"NORMAL"}}];
  tt.x = {x + 800}; tt.y = {y + 40};
  figma.currentPage.appendChild(tt);
  var t = figma.createText();
  t.fontName = {{family:'Inter',style:'Regular'}};
  t.characters = 'Helpful tooltip text here';
  t.fontSize = 12;
  t.fills = [{{type:'SOLID',color:{{r:1,g:1,b:1}}}}];
  t.x = 12; t.y = 10;
  tt.appendChild(t);
  // Arrow
  var arr = figma.createText();
  arr.fontName = {{family:'Inter',style:'Regular'}};
  arr.characters = '▲';
  arr.fontSize = 10;
  arr.fills = [{{type:'SOLID',color:{{r:0.075,g:0.141,b:0.271}}}}];
  arr.x = {x + 890}; arr.y = {y + 74};
  figma.currentPage.appendChild(arr);
  return JSON.stringify({{ok:true}});
}})();
""")


# ── Utility ────────────────────────────────────────────────────────────────────
def _hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    return (
        round(int(h[0:2], 16) / 255, 3),
        round(int(h[2:4], 16) / 255, 3),
        round(int(h[4:6], 16) / 255, 3),
    )


if __name__ == "__main__":
    build()
