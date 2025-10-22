"""Quick test harness to exercise the mcp-d3-stdio-custom server tools.
This script imports the TOOLS mapping from the server module and calls several tools with
sample payloads. Each tool will save an HTML file in the server's html-charts directory.

Finally this script creates `all_d3_charts_preview.html` in the same folder which embeds
all the generated HTML files in stacked iframes so you can preview them in one page.
"""
import importlib
import os
from pathlib import Path

SERVER_MOD = 'mcp_d3_stdio_server'
ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / 'html-charts'
OUTDIR.mkdir(parents=True, exist_ok=True)

# import server module from this directory
import sys
sys.path.insert(0, str(ROOT))
server = importlib.import_module(SERVER_MOD)

# mapping of tool name -> sample args
SAMPLES = {
    'line': {'title':'Sample Line','data':{'labels':['Jan','Feb','Mar','Apr'],'datasets':[{'label':'Series A','data':[10,30,20,40],'backgroundColor':'#1f77b4'}]}},
    'bar': {'title':'Sample Bar','data':{'labels':['Q1','Q2','Q3'],'datasets':[{'label':'Revenue','data':[120,150,170],'backgroundColor':'#ff7f0e'}]}},
    'horizontal_bar': {'title':'Sample HBar','data':{'labels':['Alpha','Beta','Gamma'],'values':[5,9,3]}},
    'grouped_bar': {'title':'Sample Grouped Bar','data':{'labels':['2019','2020','2021'],'datasets':[{'label':'A','data':[10,20,30],'backgroundColor':'#2ca02c'},{'label':'B','data':[15,25,18],'backgroundColor':'#d62728'}]}},
    'stacked_bar': {'title':'Sample Stacked','data':{'labels':['P1','P2'],'datasets':[{'label':'X','data':[20,30]},{'label':'Y','data':[10,5]}]}},
    'pie': {'title':'Sample Pie','data':{'labels':['A','B','C'],'datasets':[{'data':[40,30,30],'backgroundColor':['#1f77b4','#ff7f0e','#2ca02c'] }]}},
    'donut': {'title':'Sample Donut','data':{'labels':['A','B'],'datasets':[{'data':[60,40],'backgroundColor':['#9467bd','#8c564b'] }]}},
    'bubble': {'title':'Sample Bubble','data':{'datasets':[{'label':'Bubbles','data':[{'x':10,'y':20,'r':8},{'x':30,'y':10,'r':12},{'x':20,'y':40,'r':6}], 'backgroundColor':['#1f77b4','#ff7f0e','#2ca02c']}]}},
    'heatmap': {'title':'Sample Heatmap','data':{'xLabels':['Mon','Tue','Wed','Thu'],'yLabels':['Week1','Week2'],'values':[[1,2,3,4],[2,4,1,3]]}},
    'packed': {'title':'Sample Packed','data':{'items':[{'id':'A','label':'A','value':40,'color':'#1f77b4'},{'id':'B','label':'B','value':60,'color':'#ff7f0e'},{'id':'C','label':'C','value':20,'color':'#2ca02c'}]}},
    'histogram': {'title':'Sample Histogram','data':{'values':[1,2,2,3,3,3,4,5,5,6,7,8], 'bins':6}},
    'scatter': {'title':'Sample Scatter','data':{'points':[{'x':1,'y':3},{'x':2,'y':5},{'x':3,'y':2,'r':6}] }},
    'treemap': {'title':'Sample Treemap','data':{'name':'root','children':[{'name':'A','value':30,'color':'#1f77b4'},{'name':'B','value':70,'color':'#ff7f0e'}]}},
    'tree': {'title':'Sample Tree','data':{'name':'root','children':[{'name':'child1'},{'name':'child2','children':[{'name':'leaf1'},{'name':'leaf2'}]}]}},
    'force': {'title':'Sample Force','data':{'nodes':[{'id':'n1'},{'id':'n2'},{'id':'n3'}],'links':[{'source':'n1','target':'n2'},{'source':'n2','target':'n3'}]}},
    # placeholders will still render a message
    'sankey': {'title':'Sample Sankey','data':{}},
    'choropleth': {'title':'Sample Choropleth','data':{}},
}

generated = []
for tool, args in SAMPLES.items():
    handler = server.TOOLS.get(tool)
    if not handler:
        print('No handler for', tool)
        continue
    try:
        res = handler(args)
        if isinstance(res, dict) and res.get('status') == 'ok' and res.get('path'):
            generated.append((tool, res['path']))
            print('Generated', tool, '->', res['path'])
        else:
            print('Tool', tool, 'returned', res)
    except Exception as e:
        print('Exception calling', tool, e)

# create a combined preview page with stacked iframes
preview = OUTDIR / 'all_d3_charts_preview.html'
parts = ["<html><head><meta charset='utf-8'><title>All D3 Charts Preview</title></head><body><h1>All D3 Charts Preview</h1>"]
for tool, path in generated:
    rel = os.path.relpath(path, OUTDIR)
    parts.append(f"<h2>{tool}</h2>")
    parts.append(f"<iframe src='{rel}' style='width:100%;height:560px;border:1px solid #ccc;margin-bottom:20px;'></iframe>")
parts.append('</body></html>')
preview.write_text('\n'.join(parts), encoding='utf-8')
print('Wrote preview ->', str(preview))
