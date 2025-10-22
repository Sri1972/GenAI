from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import traceback
import os
from dotenv import load_dotenv

import json
import anthropic
import re

# Added imports required by functions later in this module
import sys
import hashlib
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

# Load environment variables
load_dotenv('.env')
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')  # Put your Claude API key in .env

# Initialize Anthropic client and model default at module level so it's always defined
try:
    claude = anthropic.Anthropic(api_key=anthropic_api_key)
except Exception:
    claude = None
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

# Short-lived in-process chat memory
chat_memories = {}
MEMORY_MAX_MESSAGES = 200

server_params = StdioServerParameters(
    command="npx",
    args=["-y", r"D:\\GenAI\\MCP\\PMO\\pmo.py"]
)

async def run(query: str, chat_id: str = "default"):
    try:
        print("🚀 Starting stdio_client to MCP server...")
        async with stdio_client(server_params) as (reader, writer):
            print("✅ Connected to PMO MCP server")
            async with ClientSession(reader, writer) as session:
                print("🔧 Initializing MCP session...")
                await session.initialize()
                print("✅ MCP session initialized")

                # Tool listing
                tools_result = await session.list_tools()
                print("Available tools:", tools_result)

                # Build a rich, structured description of available tools including parameter names/types
                tool_lines = []
                for tool in tools_result.tools:
                    desc = (getattr(tool, 'description', '') or '').strip().replace('\n', ' ')
                    schema = getattr(tool, 'inputSchema', None) or {}
                    props = schema.get('properties', {}) if isinstance(schema, dict) else {}
                    required = schema.get('required', []) if isinstance(schema, dict) else []
                    params = []
                    for k, v in (props.items() if isinstance(props, dict) else []):
                        ptype = ''
                        if isinstance(v, dict):
                            ptype = v.get('type') or v.get('title') or ''
                        params.append("{}{}".format(k, (' (' + str(ptype) + ')') if ptype else ''))
                    param_str = ", ".join(params) if params else "no parameters"
                    req_str = (" Required: {}.".format(', '.join(required))) if required else ""
                    tool_lines.append("- {}: {} Params: {}.{}".format(tool.name, desc, param_str, req_str))
                tool_descriptions = "\n".join(tool_lines)

                system_instructions = (
                    "You are a PMO assistant connected to a PMO MCP server.\n"
                    "Rules:\n"
                    "- For any question requiring factual project or resource data, you MUST return a JSON tool call as the very first thing in your response.\n"
                    "- The JSON must be a single object in this exact form with no leading text: {\"tool\":\"<tool_name>\", \"arguments\": {...}}\n"
                    "- If clarification is required, ask a short clarifying question instead of guessing data.\n\n"
                    "Available tools and their parameters:\n"
                ) + tool_descriptions + (
                    "\n\nExamples (when data is needed, respond exactly with the JSON object first):\n"
                    "User: \"List all projects in the PMO system.\"\n"
                    "Assistant:\n"
                    "{\"tool\":\"get_all_projects\",\"arguments\":{}}\n\n"
                    "User: \"Show planned vs actual hours for resource 42 from 2025-01-01 to 2025-12-31 monthly.\"\n"
                    "Assistant:\n"
                    "{\"tool\":\"get_resource_allocation_planned_actual\",\"arguments\":{\"resource_id\":42,\"start_date\":\"2025-01-01\",\"end_date\":\"2025-12-31\",\"interval\":\"Monthly\"}}\n\n"
                    "User: \"Give me projects in Market & Sell portfolio with hours and costs.\"\n"
                    "Assistant:\n"
                    "{\"tool\":\"get_filtered_projects\",\"arguments\":{\"fields\":[\"project_name\",\"project_resource_hours_planned\",\"project_resource_cost_planned\"],\"filters\":[{\"column\":\"strategic_portfolio\",\"operator\":\"=\",\"value\":\"Market & Sell\"}]}}\n\n"
                    "If you need to provide commentary or explanation, put it AFTER the JSON object. The client will execute the first JSON object it finds and then provide the tool output back to you for any further reasoning.\n"
                )

                system_messages = [
                    {"role": "system", "content": system_instructions}
                ]

                # Build a richer system context by injecting resources and prompts from the MCP server
                resources_result = await session.list_resources()
                prompts_result = await session.list_prompts()
                resources = getattr(resources_result, 'resources', [])
                prompts = getattr(prompts_result, 'prompts', [])

                # Inject resource and prompt contents into the system context so Claude can use them
                for resource in resources:
                    content = getattr(resource, 'content', None) or getattr(resource, '_content', None)
                    if isinstance(content, str) and content.strip():
                        system_messages.append({"role": "system", "content": f"[{resource.name}] {content}"})
                for prompt in prompts:
                    content = getattr(prompt, 'content', None) or getattr(prompt, '_content', None)
                    if isinstance(content, str) and content.strip():
                        system_messages.append({"role": "system", "content": f"[{prompt.name}] {content}"})

                # Prepare the initial user message
                user_message = {"role": "user", "content": query}

                # Load or initialize short-lived in-process conversation memory for this chat_id
                conversation_messages = chat_memories.get(chat_id, []).copy()
                if not isinstance(conversation_messages, list):
                    conversation_messages = []
                # Append the new user message as the latest turn
                conversation_messages.append(user_message)

                # Build a single string system_text from system_messages for Anthropic calls
                system_text = "\n".join([m['content'] for m in system_messages])

                # Helper: if assistant returns full HTML (chart), save to html-charts/ and return filepath

                def save_html_response_if_needed(text: str, query_text: str = None, prefix: str = "chart") -> str | None:
                    """If `text` looks like an HTML document, save it to MCP-CLIENT/html-charts and
                    return the absolute path. Otherwise return None.
                    """
                    # Expanded markers to include common JS-only data fragments such as `const data =` or `window.__chart_data`
                    markers = ["<!DOCTYPE html", "<html", "<script id=\"chart-data\"", "<div id=\"chart\"", "const data =", "var data =", "let data =", "window.__chart_data", "window.__chart"]
                    if not any(m in text for m in markers):
                        return None
                    try:
                        outdir = Path(__file__).resolve().parent / "html-charts"
                        outdir.mkdir(parents=True, exist_ok=True)
                        slug = ""
                        if query_text:
                            slug = re.sub(r'[^A-Za-z0-9_-]', '_', query_text)[:40]
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        h = hashlib.sha1(text.encode('utf-8')).hexdigest()[:6]
                        if slug:
                            filename = f"{prefix}_{slug}_{ts}_{h}.html"
                        else:
                            filename = f"{prefix}_{ts}_{h}.html"
                        filepath = outdir / filename
                        # Write as bytes and ensure fully flushed to disk to avoid truncation
                        with open(filepath, 'wb') as f:
                            data = text.encode('utf-8')
                            f.write(data)
                            f.flush()
                            try:
                                os.fsync(f.fileno())
                            except Exception:
                                pass
                        # Verify file size
                        try:
                            if filepath.stat().st_size != len(data):
                                print(f"Warning: written file size {filepath.stat().st_size} differs from expected {len(data)}")
                        except Exception:
                            pass

                        # If Claude returned an HTML fragment that contains a JS `const data = ...` but
                        # lacks a Chart initialization (common when responses truncated), attempt to repair
                        def _repair_claude_html(file_path: Path) -> None:
                            try:
                                txt = file_path.read_text(encoding='utf-8', errors='replace')
                                # If file already has embedded chart-data or Chart init, nothing to do
                                if '<script id="chart-data"' in txt or 'new Chart(' in txt or 'Chart(' in txt:
                                    return
                                # Try to extract `const data = ...;` or `var data = ...;` JSON-like block
                                m = re.search(r"(?:const|var|let)\s+data\s*=\s*(\[\s*[\s\S]*?\])\s*;", txt, re.IGNORECASE)
                                # detect existing canvas id in the fragment so repaired HTML uses the same id
                                canvas_m = re.search(r"<canvas[^>]*id=[\"']([^\"']+)[\"']", txt, re.IGNORECASE)
                                canvas_id_detected = canvas_m.group(1) if canvas_m else 'hoursChart'
                                if not m:
                                    # also try to find a top-level array starting with '[' in the body
                                    m2 = re.search(r"(\[\s*\{[\s\S]*?\}\s*\])", txt, re.IGNORECASE)
                                    if m2:
                                        json_text = m2.group(1)
                                    else:
                                        # As a last-resort, attempt to extract 'stat-card' label/value pairs from truncated HTML
                                        # Many Claude-generated fragments include boxed stat cards; use them to build a simple chart
                                        stats = []
                                        try:
                                            pairs = re.findall(r"<div[^>]*class=[\"']stat-card[\"'][^>]*>[\s\S]*?<div[^>]*class=[\"']stat-label[\"'][^>]*>(.*?)</div>\s*<div[^>]*class=[\"']stat-value[\"'][^>]*>(.*?)</div>", txt, re.IGNORECASE)
                                            for label, val in pairs:
                                                lbl = re.sub(r"<[^>]+>", "", label).strip()
                                                vstr = re.sub(r"[^0-9.\-]", "", val)
                                                try:
                                                    v = float(vstr) if vstr not in (None, "") else 0.0
                                                except Exception:
                                                    v = 0.0
                                                stats.append((lbl or 'Value', v))
                                        except Exception:
                                            stats = []

                                        if stats:
                                            labels = [s[0] for s in stats]
                                            datasets = [{
                                                'label': 'Value',
                                                'data': [s[1] for s in stats],
                                                'borderColor': '#1f77b4',
                                                'backgroundColor': '#1f77b4'
                                            }]
                                            chart_payload = {'labels': labels, 'datasets': datasets}
                                            # Reuse minimal repair template but try to preserve original title and canvas id
                                            try:
                                                title_m = re.search(r"<title[^>]*>([^<]+)</title>", txt, re.IGNORECASE)
                                                safe_title = title_m.group(1).strip() if title_m else 'Repaired Chart'
                                            except Exception:
                                                safe_title = 'Repaired Chart'
                                            # Use detected canvas id and ensure initialization happens after load
                                            template = """<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>__TITLE__</title>
<style>body{font-family:Segoe UI,Arial,sans-serif;margin:20px;background:#f5f5f5} .container{max-width:1100px;margin:0 auto;background:#fff;padding:20px;border-radius:8px} .chart-wrap{position:relative;height:520px} canvas{width:100% !important;height:100% !important;display:block}</style>
</head>
<body>
<div class='container'><h3>Repaired Chart (extracted stats)</h3><div class='chart-wrap'><canvas id='__CANVAS_ID__'></canvas></div></div>
<script id='chart-data' type='application/json'>__CHART_PAYLOAD__</script>
<script>(function(){
  function initChart(){
    try{
      var payload=JSON.parse(document.getElementById('chart-data').textContent||'{}');
      payload.datasets = payload.datasets || [];
      payload.datasets.forEach(function(ds){
        ds.data = (ds.data||[]).map(function(v){ if(v==null) return 0; if(typeof v==='number') return v; var n=Number(String(v).replace(/[^0-9.\-]/g,'')); return Number.isFinite(n)?n:0; });
        ds.borderColor = ds.borderColor || '#777';
        ds.backgroundColor = ds.borderColor || ds.borderColor; ds.borderWidth = ds.borderWidth || 1;
      });
      var ctx = document.getElementById('__CANVAS_ID__').getContext('2d');
      new Chart(ctx, { type: 'bar', data: payload, options: { responsive:true, maintainAspectRatio:false, scales: { y: { beginAtZero:true } } } });
    }catch(e){ console.error('repair render error', e); }
  }
  if (typeof Chart === 'undefined'){
    var s = document.createElement('script'); s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'; s.onload = initChart; s.onerror = function(){ console.error('Failed to load Chart.js UMD'); initChart(); }; document.head.appendChild(s);
  } else { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initChart); else initChart(); }
})();</script>
</body>
</html>"""
                                            out_html = template.replace('__TITLE__', safe_title).replace('__CANVAS_ID__', canvas_id_detected).replace('__CHART_PAYLOAD__', json.dumps(chart_payload))
                                            file_path.write_text(out_html, encoding='utf-8')
                                            print('Repaired saved HTML from stat-cards to include a chart:', str(file_path))
                                            return

                                        # No JSON and no stat-cards found — give up on repair here
                                        return
                                else:
                                    json_text = m.group(1)
                                # Parse extracted JSON
                                try:
                                    parsed = json.loads(json_text)
                                except Exception:
                                    # attempt to clean trailing commas
                                    cleaned = re.sub(r',\s*(?=[\]\}])', '', json_text)
                                    parsed = json.loads(cleaned)
                                # Build a minimal payload suitable for Chart.js multi-line/time-series
                                labels = []
                                datasets = []
                                if isinstance(parsed, list) and parsed:
                                    sample = parsed[0]
                                    # choose label key heuristically
                                    label_key = None
                                    for k in sample.keys():
                                        lk = k.lower()
                                        if any(x in lk for x in ('month','date','period','time','week')):
                                            label_key = k
                                            break
                                chart_payload = {'labels': labels, 'datasets': datasets}
                                # Minimal Chart.js page with embedded payload (use detected canvas id and deferred init)
                                template = """<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Repaired Chart</title>
<style>body{font-family:Segoe UI,Arial,sans-serif;margin:20px;background:#f5f5f5} .container{max-width:1100px;margin:0 auto;background:#fff;padding:20px;border-radius:8px} .chart-wrap{position:relative;height:520px} canvas{width:100% !important;height:100% !important;display:block}</style>
</head>
<body>
<div class='container'><h3>Repaired Chart (extracted data)</h3><div class='chart-wrap'><canvas id='__CANVAS_ID__'></canvas></div></div>
<script id='chart-data' type='application/json'>__CHART_PAYLOAD__</script>
<script>(function(){
  function initChart(){
    try{
      var payload=JSON.parse(document.getElementById('chart-data').textContent||'{}');
      payload.datasets = payload.datasets || [];
      payload.datasets.forEach(function(ds){ ds.data = (ds.data||[]).map(function(v){ if (v === null || v === undefined) return 0; if (typeof v === 'number') return v; var n = Number(String(v).replace(/[^0-9.\-]/g, '')); return Number.isFinite(n) ? n : 0; }); ds.backgroundColor = ds.backgroundColor || ds.borderColor || '#777'; ds.borderColor = ds.borderColor || ds.backgroundColor; ds.borderWidth = ds.borderWidth || 1; });
      var ctx = document.getElementById('__CANVAS_ID__').getContext('2d');
      new Chart(ctx, { type: 'bar', data: payload, options: { responsive:true, maintainAspectRatio:false, scales: { y: { beginAtZero:true } } } });
    }catch(e){ console.error('repair render error', e); }
  }
  if (typeof Chart is 'undefined'){
    var s = document.createElement('script'); s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'; s.onload = initChart; s.onerror = function(){ console.error('Failed to load Chart.js UMD'); initChart(); }; document.head.appendChild(s);
  } else { if (document.readyState is 'loading') document.addEventListener('DOMContentLoaded', initChart); else initChart(); }
})();</script>
</body>
</html>"""
                                out_html = template.replace('__CANVAS_ID__', canvas_id_detected).replace('__CHART_PAYLOAD__', json.dumps(chart_payload))
                                # overwrite file with repaired HTML
                                file_path.write_text(out_html, encoding='utf-8')
                                print('Repaired saved HTML to include chart initialization:', str(file_path))
                            except Exception as e:
                                print('Could not repair saved HTML:', e)

                        try:
                            _repair_claude_html(filepath)
                        except Exception:
                            pass

                        return str(filepath)
                    except Exception as e:
                        print("Failed to save HTML to file:", e)
                        return None

                # Automatic chart generation: if the user asked for a chart and we have recent tool output, spawn the chart generator
                def try_auto_generate_chart_from_last_tool_output(user_query: str):
                    # Detect chart intent
                    if not re.search(r"\b(chart|plot|render|visuali[sz]e|graph)\b", user_query, re.IGNORECASE):
                        return None
                    # Find the most recent TOOL OUTPUT in conversation_messages
                    last_tool_data = None
                    last_tool_name = None
                    for msg in reversed(conversation_messages):
                        if msg.get('role') == 'user' and isinstance(msg.get('content'), str) and msg.get('content', '').startswith('[TOOL OUTPUT -'):
                            # content is like: [TOOL OUTPUT - tool_name]\n<json or text>
                            parts = msg['content'].split('\n', 1)
                            header = parts[0]
                            m = re.match(r"\[TOOL OUTPUT - ([^\]]+)\]", header)
                            if m:
                                last_tool_name = m.group(1)
                            last_tool_data = parts[1] if len(parts) > 1 else ''
                            break
                    if not last_tool_data:
                        return None

                    # Helper: try to parse the last tool payload into usable records
                    def parse_tool_payload(payload: str):
                        try:
                            parsed = json.loads(payload)
                        except Exception:
                            # sometimes payload is double-encoded or contains leading text; try to extract first {...} or [..]
                            start = payload.find('{')
                            if start == -1:
                                start = payload.find('[')
                            end = payload.rfind('}')
                            if start != -1 and end != -1 and end > start:
                                try:
                                    return json.loads(payload[start:end+1])
                                except Exception:
                                    return None
                            try:
                                return json.loads(payload.strip())
                            except Exception:
                                return None
                        return parsed

                    dataset_obj = parse_tool_payload(last_tool_data)

                    # Compose input JSON for the spawnable: include instructions and the dataset
                    spawn_input = {
                        "query": (
                            "Create a JavaScript multi-line chart (lines only) from the following dataset. "
                            "Requirements: legend below the chart, tooltip, axis stroke CSS, embed the data as JSON into the generated HTML. "
                            "Do not include external watchers; return full HTML markup.\n\nDATA:\n" + last_tool_data
                        )
                    }

                    # Run the spawnable generate_chart_spawnable.py using the venv python if provided, else current python
                    try:
                        script_path = str(Path(__file__).resolve().parent / 'generate_chart_spawnable.py')
                        python_exec = os.getenv('VENV_PYTHON') or sys.executable
                        # Honor CHART_ADAPTER_ONLY to skip spawnable and use HTTP adapter/local renderer only
                        if os.getenv('CHART_ADAPTER_ONLY', '').lower() in ('1', 'true', 'yes'):
                            proc = None
                        else:
                            proc = subprocess.run([python_exec, '-u', script_path], input=json.dumps(spawn_input), text=True, capture_output=True, timeout=int(os.getenv('CHART_SPAWNABLE_TIMEOUT', '120')))
                    except Exception as e:
                        print("Failed to spawn chart generator:", e)
                        proc = None

                    html_output = None
                    if proc is not None:
                        if proc.returncode != 0:
                            # Quietly note failure and avoid dumping full stderr (which contains anyio/httpx TaskGroup stack traces)
                            print(f"Chart generator spawnable failed (rc={proc.returncode}). Falling back to adapter/local renderer.")
                            # Optionally include a short stderr snippet for diagnostics without flooding the console
                            try:
                                stderr_snippet = (proc.stderr or '').strip()
                                if stderr_snippet:
                                    print("Chart generator stderr (snippet):", stderr_snippet[:300].replace('\n', ' '))
                            except Exception:
                                pass
                        else:
                            html_output = (proc.stdout or '')

                    # If spawnable failed or produced no HTML, attempt to call a local HTTP adapter as a quieter fallback
                    if not html_output:
                        adapter_url = os.getenv('CHART_ADAPTER_URL', 'http://localhost:8000/generate-chart')
                        try:
                            req_data = json.dumps({"query": spawn_input['query']}).encode('utf-8')
                            req = urllib.request.Request(adapter_url, data=req_data, headers={'Content-Type': 'application/json'})
                            with urllib.request.urlopen(req, timeout=30) as resp:
                                ctype = resp.headers.get('Content-Type', '')
                                body = resp.read()
                                text = body.decode('utf-8', errors='replace')
                                # Prefer raw HTML responses
                                if 'html' in ctype.lower() or text.strip().startswith('<'):
                                    html_output = text
                                    print(f"✅ Adapter returned HTML from {adapter_url}")
                                else:
                                    # Try to parse JSON-ish response and extract likely HTML
                                    try:
                                        j = json.loads(text)
                                        if isinstance(j, dict):
                                            html_output = j.get('result') or j.get('html') or j.get('content')
                                            if html_output and not isinstance(html_output, str):
                                                html_output = json.dumps(html_output)
                                    except Exception:
                                        pass
                        except Exception as e:
                            # Be quiet about adapter failure but emit a short message for diagnostics
                            print("HTTP adapter call failed (will fallback to local renderer):", str(e))

                    # If spawnable produced HTML, try to save it first
                    if html_output:
                        saved = save_html_response_if_needed(html_output, user_query, prefix="auto_chart")
                        # Quick validation: ensure embedded chart-data exists and is non-empty
                        def html_has_embedded_data(html_text: str) -> bool:
                            if '<script id="chart-data"' in html_text:
                                # crude check for non-empty JSON
                                m = re.search(r'<script id="chart-data".*?>([\s\S]*?)</script>', html_text, re.IGNORECASE)
                                if m:
                                    content = m.group(1).strip()
                                    return len(content) > 20
                            # fallback: look for recognizable dataset keys
                            return bool(re.search(r'"capacity"|"planned"|"actual"|"capacity_hours"|"planned_hours"', html_text, re.IGNORECASE))

                        if saved and html_has_embedded_data(html_output):
                            print("✅ Auto-generated chart saved to:", saved)
                            conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {saved}"})
                            chat_memories[chat_id] = conversation_messages[-MEMORY_MAX_MESSAGES:]
                            return f"HTML_SAVED:{saved}"
                        # If HTML exists but has no embedded data, fall through to local renderer

                    # If spawnable failed or produced HTML without embedded data, build our own HTML from dataset_obj
                    def render_chart_html_from_dataset(data_obj, title_text: str = "Chart", user_query: str = None) -> str:
                        """Normalized renderer: default to line charts for time-series and fall back to grouped bars when the data clearly indicates per-project planned/actual values.

                        Returns full HTML string embedding JSON in <script id="chart-data"> and initializing Chart.js UMD.
                        """
                        # Normalize records
                        records = []
                        if isinstance(data_obj, dict) and 'result' in data_obj:
                            records = data_obj.get('result') or []
                        elif isinstance(data_obj, list):
                            records = data_obj
                        elif isinstance(data_obj, dict):
                            # try to find inner list
                            for v in data_obj.values():
                                if isinstance(v, list):
                                    records = v
                                    break
                        records = [r for r in records if isinstance(r, dict)]

                        # Heuristics
                        label_field = None
                        numeric_fields = []
                        name_field = None
                        if records:
                            sample = records[0]
                            for k in sample.keys():
                                lk = k.lower()
                                if any(x in lk for x in ("month", "date", "week", "period", "time")):
                                    label_field = k
                                    break
                            for k in sample.keys():
                                lk = k.lower()
                                if any(x in lk for x in ("project", "name", "title", "project_name")) and isinstance(sample.get(k), str):
                                    name_field = k
                                    break
                            # gather numeric fields
                            for k, v in sample.items():
                                if k == label_field:
                                    continue
                                lk = k.lower()
                                if any(sub in lk for sub in ("cumul", "cumulative", "running_total", "total")):
                                    continue
                                if isinstance(v, (int, float)):
                                    numeric_fields.append(k)

                        # Build datasets
                        labels = []
                        datasets = []
                        chart_type = 'line'

                        # Project-mode grouped bars if we have a project/name label and planned/actual-like numeric fields
                        planned_keys = []
                        actual_keys = []
                        if records and name_field:
                            for k in records[0].keys():
                                lk = k.lower()
                                if re.search(r'planned|plan|budget', lk):
                                    planned_keys.append(k)
                                if re.search(r'actual|spent|spent_amount|cost|expense', lk):
                                    actual_keys.append(k)
                            if planned_keys or actual_keys:
                                chart_type = 'bar'
                                labels = [str(r.get(name_field, '')) for r in records]
                                def extract_vals(keys):
                                    vals = []
                                    for r in records:
                                        v = None
                                        for k in keys:
                                            if k in r and r.get(k) not in (None, ''):
                                                v = r.get(k)
                                                break
                                        try:
                                            vals.append(float(v) if v is not None else 0.0)
                                        except Exception:
                                            vals.append(0.0)
                                    return vals
                                palette = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]
                                if planned_keys:
                                    datasets.append({"label": "Planned", "data": extract_vals(planned_keys), "backgroundColor": palette[0], "borderColor": palette[0]})
                                if actual_keys:
                                    datasets.append({"label": "Actual", "data": extract_vals(actual_keys), "backgroundColor": palette[1], "borderColor": palette[1]})
                                # if no planned/actual but there are numeric_fields, include each numeric as a dataset
                                if not datasets and numeric_fields:
                                    for idx, f in enumerate(numeric_fields):
                                        vals = []
                                        for r in records:
                                            try:
                                                vals.append(float(r.get(f, 0) if r.get(f) is not None else 0))
                                            except Exception:
                                                vals.append(0)
                                        color = palette[idx % len(palette)]
                                        datasets.append({"label": f, "data": vals, "backgroundColor": color, "borderColor": color})

                        # Pie/doughnut detection: single numeric field per categorical label -> render a pie
                        if chart_type == 'line' and records:
                            def _is_time_like(key):
                                return key and any(x in key.lower() for x in ("month", "date", "week", "period", "time"))

                            # Choose category field: prefer name_field, else a non-time string key
                            category_field = name_field or label_field
                            if not category_field:
                                for k, v in records[0].items():
                                    if isinstance(v, str) and not _is_time_like(k):
                                        category_field = k
                                        break

                            # Identify numeric fields present in the sample (exclude the chosen category)
                            candidate_numeric_fields = []
                            if category_field:
                                for k, v in records[0].items():
                                    if k == category_field:
                                        continue
                                    try:
                                        if isinstance(v, (int, float)):
                                            candidate_numeric_fields.append(k)
                                        elif isinstance(v, str) and re.match(r'^[\d,\.\-\s]+$', v.strip()):
                                            candidate_numeric_fields.append(k)
                                    except Exception:
                                        pass

                                # If exactly one numeric field present, render pie chart
                                if len(candidate_numeric_fields) == 1:
                                    num_key = candidate_numeric_fields[0]
                                    chart_type = 'pie'
                                    labels = [str(r.get(category_field, '')) for r in records]
                                    vals = []
                                    for r in records:
                                        try:
                                            raw = r.get(num_key, 0)
                                            if raw is None:
                                                raw = 0
                                            vals.append(float(re.sub(r'[^0-9.\-]', '', str(raw)) or 0))
                                        except Exception:
                                            vals.append(0)
                                    # Per-segment colors
                                    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
                                    bg_colors = [palette[i % len(palette)] for i in range(len(labels))]
                                    datasets.append({"label": num_key, "data": vals, "backgroundColor": bg_colors, "borderColor": bg_colors})

                        # Honor explicit user request for pie/doughnut charts or convert single-dataset bars into a pie
                        try:
                            if user_query and re.search(r'\b(pie|donut|doughnut)\b', user_query, re.IGNORECASE):
                                # choose doughnut if requested explicitly
                                desired = 'doughnut' if re.search(r'\b(donut|doughnut)\b', user_query, re.IGNORECASE) else 'pie'
                                # If we already have multiple datasets (e.g., grouped bars), collapse to single totals or pick a sensible one
                                if datasets and len(datasets) > 1:
                                    # prefer a dataset labeled 'Planned' or 'Total' if present
                                    chosen = None
                                    for ds in datasets:
                                        if isinstance(ds.get('label', ''), str) and re.search(r'planned|plan|total', ds['label'], re.IGNORECASE):
                                            chosen = ds
                                            break
                                    if not chosen:
                                        # sum across datasets to create totals per label
                                        sums = [0 for _ in labels]
                                        for ds in datasets:
                                            for i, v in enumerate(ds.get('data', [])):
                                                try:
                                                    sums[i] += float(v or 0)
                                                except Exception:
                                                    pass
                                        palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
                                        bg_colors = [palette[i % len(palette)] for i in range(len(labels))]
                                        datasets = [{"label": "Total", "data": sums, "backgroundColor": bg_colors, "borderColor": bg_colors}]
                                    else:
                                        data = chosen.get('data', [])
                                        bg = chosen.get('backgroundColor', chosen.get('borderColor'))
                                        if not isinstance(bg, list):
                                            palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
                                            bg_colors = [palette[i % len(palette)] for i in range(len(labels))]
                                        else:
                                            bg_colors = bg
                                        datasets = [{"label": chosen.get('label', 'Value'), "data": data, "backgroundColor": bg_colors, "borderColor": bg_colors}]
                                # If we have a single dataset already but it's a bar, convert to pie/doughnut
                                elif datasets and len(datasets) == 1:
                                    # ensure backgroundColor is per-segment array
                                    ds = datasets[0]
                                    if not isinstance(ds.get('backgroundColor'), list):
                                        palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
                                        bg_colors = [palette[i % len(palette)] for i in range(len(labels))]
                                    else:
                                        bg_colors = ds.get('backgroundColor')
                                    datasets = [{"label": ds.get('label', 'Value'), "data": ds.get('data', []), "backgroundColor": bg_colors, "borderColor": bg_colors}]
                                chart_type = desired
                        except Exception:
                            pass

                        # Time-series / multi-line fallback
                        if chart_type == 'line':
                            if records:
                                for r in records:
                                    labels.append(str(r.get(label_field)) if label_field and label_field in r else '')
                                # if numeric_fields empty, attempt to infer any numeric columns across records
                                if not numeric_fields and records:
                                    sample = records[0]
                                    for k, v in sample.items():
                                        if k == label_field:
                                            continue
                                        try:
                                            vals = [float(rr.get(k, 0) or 0) for rr in records]
                                            if any(vv != 0 for vv in vals):
                                                numeric_fields.append(k)
                                        except Exception:
                                            pass
                                palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
                                for idx, f in enumerate(numeric_fields):
                                    vals = []
                                    for r in records:
                                        try:
                                            v = r.get(f, None)
                                            vals.append(float(v) if v is not None else None)
                                        except Exception:
                                            vals.append(None)
                                    color = palette[idx % len(palette)]
                                    datasets.append({"label": f, "data": vals, "borderColor": color, "backgroundColor": color, "fill": False})

                        # If still no datasets, create a tiny placeholder to avoid empty-chart errors
                        if not datasets:
                            labels = labels or ["x"]
                            datasets = [{"label": "value", "data": [0 for _ in labels], "borderColor": "#777", "backgroundColor": "#bbb"}]

                        chart_payload = {"labels": labels, "datasets": datasets}

                        # Unified Chart.js HTML template that adapts to chart_type
                        template = """<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>__TITLE__</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:20px;background:#f5f5f5}
.container{max-width:1100px;margin:0 auto;background:#fff;padding:20px;border-radius:8px;box-shadow:0 4px 18px rgba(0,0,0,0.08)}
.chart-wrap{position:relative;height:520px;padding:10px}
canvas{width:100% !important;height:100% !important}
.legend-box{background:#ffffff;border:1px solid rgba(0,0,0,0.06);padding:12px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.04);margin-top:12px;display:flex;justify-content:center}
.legend-custom{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.legend-item{display:flex;align-items:center;gap:10px;font-size:13px;color:#fff;padding:8px 12px;border-radius:8px;font-weight:600}
.legend-color{width:12px;height:12px;border-radius:2px;display:inline-block;margin-right:8px}
.info{font-size:13px;color:#666;text-align:center;margin-top:10px}
</style>
</head>
<body>
<div class='container'>
<h2>__TITLE__</h2>
<div class='chart-wrap'>
<canvas id='hoursChart'></canvas>
</div>
<div class='legend-box' aria-hidden='false'>
  <div id='chart-legend' class='legend-custom'></div>
</div>
<div class='info'>Generated from PMO data</div>
</div>
<script id='chart-data' type='application/json'>
__CHART_PAYLOAD__
</script>
<script>
(function(){
  try{
    var chartType = '__CHART_TYPE__';
    var payload = JSON.parse(document.getElementById('chart-data').textContent || '{}');
    payload.datasets = payload.datasets || [];
    payload.datasets.forEach(function(ds){
      ds.data = (ds.data || []).map(function(v){ if (v === null || v === undefined) return 0; if (typeof v === 'number') return v; var n = Number(String(v).replace(/[^0-9.\-]/g, '')); return Number.isFinite(n) ? n : 0; });
      ds.backgroundColor = ds.backgroundColor || ds.borderColor || '#777';
      ds.borderColor = ds.borderColor || ds.backgroundColor;
      ds.borderWidth = ds.borderWidth != null ? ds.borderWidth : 1;
    });

    var ctx = document.getElementById('hoursChart').getContext('2d');
    var opts = {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: true } },
      plugins: { legend: { display: false } }
    };
    if (chartType === 'bar') opts.scales.x = { stacked: false };

    try{ new Chart(ctx, { type: chartType, data: payload, options: opts }); }catch(e){ console.error('Chart init error', e); }

    // build legend: for pie charts create segment-level legend, otherwise dataset totals
    var legendEl = document.getElementById('chart-legend'); legendEl.innerHTML = '';
    if (chartType === 'pie' || chartType === 'doughnut'){
      var labels = payload.labels || [];
      var ds = payload.datasets && payload.datasets[0] || { data: [], backgroundColor: [] };
      var bg = ds.backgroundColor || [];
      for(var i=0;i<labels.length;i++){
        var val = (ds.data && ds.data[i]) || 0;
        var color = Array.isArray(bg) ? (bg[i] || '#777') : (bg || '#777');
        var item = document.createElement('div'); item.className='legend-item'; item.style.background = color;
        var sw = document.createElement('span'); sw.className='legend-color'; sw.style.background = color; sw.style.display='inline-block'; sw.style.width='12px'; sw.style.height='12px'; sw.style.marginRight='8px'; sw.style.borderRadius='2px';
        var lbl = document.createElement('span'); lbl.textContent = labels[i] + ' — ' + (Number(val)||0).toLocaleString();
        item.appendChild(sw); item.appendChild(lbl); legendEl.appendChild(item);
      }
    } else {
      payload.datasets.forEach(function(ds){
        var total = 0; for(var i=0;i<ds.data.length;i++){ var v = ds.data[i]; if(typeof v === 'number' && !isNaN(v)) total += v; }
        var item = document.createElement('div'); item.className='legend-item'; item.style.background = ds.backgroundColor || '#777';
        var sw = document.createElement('span'); sw.className='legend-color'; sw.style.background = (ds.backgroundColor||'#777'); sw.style.display='inline-block'; sw.style.width='12px'; sw.style.height='12px'; sw.style.marginRight='8px'; sw.style.borderRadius='2px';
        var lbl = document.createElement('span'); lbl.textContent = ds.label + ' — ' + total.toLocaleString();
        item.appendChild(sw); item.appendChild(lbl); legendEl.appendChild(item);
      });
    }

  }catch(e){ console.error('render error', e); }
})();
</script>
</body>
</html>"""

                        html_out = template.replace('__TITLE__', str(title_text)).replace('__CHART_PAYLOAD__', json.dumps(chart_payload)).replace('__CHART_TYPE__', chart_type)
                        return html_out

                    html_output = render_chart_html_from_dataset(dataset_obj, title_text="Auto-generated Chart", user_query=user_query)
                    saved = save_html_response_if_needed(html_output, user_query, prefix="auto_chart")
                    if saved:
                        print("✅ Auto-generated chart saved to:", saved)
                        conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {saved}"})
                        chat_memories[chat_id] = conversation_messages[-MEMORY_MAX_MESSAGES:]
                        return f"HTML_SAVED:{saved}"
                    return None

                # If this user query appears to request a chart and we have recent tool output, try auto-generate now and return early
                auto_generated = try_auto_generate_chart_from_last_tool_output(query)
                if auto_generated:
                    return auto_generated

                # Iterative tool-calling loop driven by Claude JSON responses
                max_iterations = 3
                iteration = 0
                last_tool_output = None

                # use module-level `re` imported at top; do not re-import here to avoid closure issues
                def extract_json_from_text(text: str):
                    # Try direct parse, fenced JSON, or first {...} block
                    try:
                        return json.loads(text)
                    except Exception:
                        m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
                        candidate = None
                        if m:
                            candidate = m.group(1)
                        else:
                            start = text.find('{')
                            end = text.rfind('}')
                            if start != -1 and end != -1 and end > start:
                                candidate = text[start:end+1]
                        if candidate:
                            try:
                                return json.loads(candidate)
                            except Exception:
                                return None
                        return None

                # Iterative Claude loop: request -> optional tool call -> feed tool output back -> repeat
                while iteration < max_iterations:
                    iteration += 1
                    try:
                        response = claude.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=1000,
                            system=system_text,
                            messages=conversation_messages
                        )
                    except Exception as e:
                        if hasattr(anthropic, "NotFoundError") and isinstance(e, getattr(anthropic, "NotFoundError")):
                            print(f"ERROR: Anthropic model '{CLAUDE_MODEL}' not found. Set CLAUDE_MODEL in .env to a supported model id (check Anthropic Console).")
                            return f"ERROR: Anthropic model '{CLAUDE_MODEL}' not found. Update CLAUDE_MODEL and retry."
                        print("Anthropic API error:", e)
                        traceback.print_exc()
                        return f"ERROR: Anthropic API request failed: {e}"

                    # Extract assistant text
                    try:
                        assistant_text = getattr(response, 'content')[0].text
                    except Exception:
                        # Be tolerant to response shape variations
                        assistant_text = str(response)

                    # Persist the assistant's raw response into the in-memory conversation so subsequent turns see it
                    conversation_messages.append({"role": "assistant", "content": assistant_text})
                    # Trim memory to limit size
                    if len(conversation_messages) > MEMORY_MAX_MESSAGES:
                        conversation_messages = conversation_messages[-MEMORY_MAX_MESSAGES:]
                    chat_memories[chat_id] = conversation_messages

                    print(f"Claude (iter {iteration}) response:\n", assistant_text)

                    # Try to extract JSON tool call from the assistant text
                    parsed = extract_json_from_text(assistant_text)

                    # Fallback heuristics for non-JSON tool hints
                    if not parsed:
                        inv_match = re.search(r'<invoke\s+name="([^"]+)"', assistant_text)
                        if inv_match:
                            parsed = {"tool": inv_match.group(1), "arguments": {}}
                        else:
                            # detect simple mentions like 'get_all_projects' or 'get_business_lines'
                            if re.search(r'\bget_all_projects\b', assistant_text):
                                parsed = {"tool": "get_all_projects", "arguments": {}}
                            elif re.search(r'\bget_business_lines\b', assistant_text):
                                parsed = {"tool": "get_business_lines", "arguments": {}}

                    # If parsed JSON indicates a tool invocation, execute it
                    if parsed and isinstance(parsed, dict) and 'tool' in parsed:
                        tool_name = parsed['tool']
                        tool_args = parsed.get('arguments', {}) or {}
                        print(f"➡️ Iteration {iteration}: Executing tool {tool_name} with args: {tool_args}")
                        try:
                            tool_result = await session.call_tool(tool_name, tool_args)
                        except Exception as tool_err:
                            print(f"Tool {tool_name} execution error: {tool_err}")
                            tool_result = {"error": str(tool_err)}

                        # Normalize tool_result into a string payload to send back to Claude
                        try:
                            if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                                result_content = json.dumps(tool_result.structuredContent, default=str)
                            elif hasattr(tool_result, 'content') and tool_result.content is not None:
                                content = tool_result.content
                                if isinstance(content, list):
                                    parts = [getattr(p, 'text', p) for p in content]
                                    if len(parts) == 1 and isinstance(parts[0], str):
                                        try:
                                            parsed_payload = json.loads(parts[0])
                                            result_content = json.dumps(parsed_payload, default=str)
                                        except Exception:
                                            result_content = parts[0]
                                    else:
                                        try:
                                            result_content = json.dumps(parts, default=str)
                                        except Exception:
                                            result_content = "\n".join(str(p) for p in parts)
                                else:
                                    if isinstance(content, (dict, list)):
                                        result_content = json.dumps(content, default=str)
                                    else:
                                        result_content = str(content)
                            else:
                                try:
                                    result_content = json.dumps(tool_result, default=str)
                                except Exception:
                                    result_content = str(tool_result)
                        except Exception:
                            result_content = str(tool_result)

                        last_tool_output = result_content
                        # Append tool output into conversation as a user message so Claude can reason about it in the next turn
                        conversation_messages.append({"role": "user", "content": f"[TOOL OUTPUT - {tool_name}]\n{result_content}"})
                        # Trim and persist memory after tool output
                        if len(conversation_messages) > MEMORY_MAX_MESSAGES:
                            conversation_messages = conversation_messages[-MEMORY_MAX_MESSAGES:]
                        chat_memories[chat_id] = conversation_messages
                        # Continue the loop to let Claude decide next action
                        continue

                    # No tool requested — treat assistant_text as final answer
                    saved_path = save_html_response_if_needed(assistant_text, query, prefix="claude_answer")
                    if saved_path:
                        print("✅ Final Claude answer saved to:", saved_path)
                        conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {saved_path}"})
                        chat_memories[chat_id] = conversation_messages[-MEMORY_MAX_MESSAGES:]
                        return f"HTML_SAVED:{saved_path}"
                    else:
                        print("✅ Final Claude answer:")
                        print(assistant_text)
                        chat_memories[chat_id] = conversation_messages[-MEMORY_MAX_MESSAGES:]
                        return assistant_text

                # If we exit loop with last_tool_output, ask Claude to reason over it (final analysis)
                if last_tool_output:
                    system_text = "\n".join([m['content'] for m in system_messages])
                    conversation_messages.append({
                        "role": "user",
                        "content": f"Here is the raw JSON result:\n{last_tool_output}\n\nNow, based on my original query ('{query}'), please compute and explain the answer. Provide only the analysis and final answer."
                    })
                    reasoning_resp = claude.messages.create(
                        model=CLAUDE_MODEL,
                        max_tokens=1000,
                        system=system_text,
                        messages=conversation_messages
                    )
                    final_text = reasoning_resp.content[0].text
                    # If Claude produced HTML for the reasoning result, save instead of printing
                    saved_path = save_html_response_if_needed(final_text, query, prefix="claude_reasoning")
                    if saved_path:
                        print("\n🤖 Claude reasoning result saved to:\n", saved_path)
                        conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {saved_path}"})
                        chat_memories[chat_id] = conversation_messages[-MEMORY_MAX_MESSAGES:]
                        return f"HTML_SAVED:{saved_path}"
                    else:
                        print("\n🤖 Claude reasoning result:\n")
                        print(final_text)
                        # Persist final reasoning in memory and return
                        conversation_messages.append({"role": "assistant", "content": final_text})
                        chat_memories[chat_id] = conversation_messages[-MEMORY_MAX_MESSAGES:]
                        return final_text

                # If nothing produced, fallback to previous simple behavior
                print("⚠️ No tool output produced and no final answer returned from Claude.")
                # Persist current memory state even if no useful output
                chat_memories[chat_id] = conversation_messages[-MEMORY_MAX_MESSAGES:]
                return None

    except Exception as e:
        print("Error during MCP session:")
        traceback.print_exc()

if __name__ == "__main__":
    print("PMO Claude REPL — type 'exit' or Ctrl-C to quit.")
    chat_id = "default"
    try:
        while True:
            try:
                query = input("\nWhat information can I get you from the PMO platform? ").strip()
            except EOFError:
                # End-of-file (e.g., piped input ended) — exit gracefully
                print("\nEOF received, exiting.")
                break
            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                print("Exiting.")
                break
            try:
                # Run the main routine using the same in-process memory (chat_id)
                asyncio.run(run(query, chat_id=chat_id))
            except KeyboardInterrupt:
                print("\nInterrupted by user. Exiting.")
                break
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye.")
