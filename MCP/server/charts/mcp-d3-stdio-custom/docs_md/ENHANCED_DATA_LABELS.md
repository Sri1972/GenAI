# Enhanced D3 Charts - Data Labels for Screenshot Export

## Problem Solved

When converting interactive D3.js charts to static images (e.g., for PowerPoint), **tooltip data is lost** because tooltips only appear on hover. This makes charts with many elements (like circle packing) difficult to interpret in screenshot form.

## Solution

We've enhanced the D3 chart templates to include **visible data labels with leader lines** that display all key information directly on the chart, making them perfect for static exports.

## Enhanced Chart Types

### 1. Circle Packing (Packed Bubble Charts)

**New Features:**
- ✅ **Leader lines** connecting circles to external labels
- ✅ **External data labels** showing `Name: Value` for each circle
- ✅ **Complete data table** below the chart with all details
- ✅ **Intelligent label positioning** to minimize overlaps
- ✅ **Hover tooltips** still available for interactive viewing

**Data Format:**
```json
{
  "items": [
    {
      "id": "Project Alpha",
      "label": "Project Alpha",
      "value": 75158,
      "color": "#2ecc71",
      "details": {
        "Portfolio": "Auto Insights",
        "Hours": "1565.8",
        "Type": "New Product"
      }
    }
  ]
}
```

**When to Use:**
- PMO project portfolios showing planned costs
- Resource allocation across teams
- Budget distribution visualizations
- Any part-to-whole data with 5-50 items

### 2. Pie/Donut Charts

**New Features:**
- ✅ **Leader lines** from pie slices to external labels
- ✅ **Percentage labels** with values: `Category: Value (25.3%)`
- ✅ **Data table** with complete breakdown
- ✅ **Total row** showing sum and 100%

**Data Format:**
```json
{
  "labels": ["Market & Sell", "Vehicles In Use", "Auto Insights", "Plan & Build"],
  "datasets": [{
    "data": [64357, 50451, 75158, 2136],
    "backgroundColor": ["#3498db", "#e74c3c", "#2ecc71", "#f39c12"]
  }]
}
```

**When to Use:**
- Portfolio distribution analysis
- Market share breakdowns
- Budget allocation by category
- Any percentage-based comparison (3-8 categories ideal)

## Configuration

### Enable/Disable Data Labels

By default, data labels are **enabled** (best for screenshots). To disable for interactive-only charts:

```python
# In d3_chart_api_server.py
script_packed(data_var='data', show_data_labels=False)  # Disable labels
script_pie(data_var='data', donut=False, show_data_labels=False)  # Disable labels
```

### Customization Options

**Circle Packing:**
- Minimum circle size for labels: `r > 15` (configurable in template)
- Label distance from circle: `labelDistance = max(d.r + 40, 60)`
- Leader line style: Dashed (`stroke-dasharray: '2,2'`)
- Table style: Alternating row colors for readability

**Pie Charts:**
- Label positioning: `outerArc.centroid(d) * 1.3` (30% beyond circle)
- Leader line style: Solid lines in slice color
- Text anchor: Automatic (start/end based on position)
- Percentage precision: `toFixed(1)` (1 decimal place)

## Comparison: Before vs. After

### Before (Interactive Only)
```
❌ Data only visible on hover
❌ Screenshot loses all tooltip information
❌ Can't identify small circles/slices
❌ No complete data reference
```

### After (Screenshot-Friendly)
```
✅ All data visible without interaction
✅ Leader lines connect labels to elements
✅ Complete data table below chart
✅ Perfect for PowerPoint/reports
✅ Interactive tooltips still available
```

## Usage Examples

### Example 1: PMO Portfolio Circle Packing

```python
import json
import subprocess
import sys

pmo_data = {
    "title": "PMO Project Portfolio",
    "data": {
        "items": [
            {
                "id": "Time To Insight",
                "label": "Time To Insight", 
                "value": 75158,
                "color": "#2ecc71",
                "details": {
                    "Portfolio": "Auto Insights",
                    "Hours": "1565.8"
                }
            },
            # ... more projects
        ]
    }
}

api_payload = {
    'tool': 'packed',
    'arguments': pmo_data
}

proc = subprocess.Popen(
    [sys.executable, 'd3_chart_api_server.py'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

input_json = json.dumps(api_payload)
stdout, stderr = proc.communicate(input=input_json + '\n', timeout=30)
response = json.loads(stdout.strip())

print(f"Chart saved: {response['path']}")
# → packed_20251120_182430_6b3d5a24.html
# → Includes leader lines, labels, and data table
```

### Example 2: Screenshot for PowerPoint

```python
from playwright.async_api import async_playwright

async def capture_chart():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1400, "height": 1200})
        
        await page.goto("file:///path/to/chart.html")
        await page.wait_for_timeout(3000)  # Wait for D3 rendering
        
        # Full page capture includes chart + data table
        await page.screenshot(path="output.png", full_page=True)
        await browser.close()

# Result: PNG with all data visible (no tooltips needed!)
```

### Example 3: Portfolio Distribution Pie Chart

```python
pie_data = {
    "title": "Portfolio Budget Distribution",
    "data": {
        "labels": ["Market & Sell", "Vehicles In Use", "Auto Insights", "Plan & Build"],
        "datasets": [{
            "data": [64357, 50451, 75158, 2136],
            "backgroundColor": ["#3498db", "#e74c3c", "#2ecc71", "#f39c12"]
        }]
    }
}

api_payload = {'tool': 'pie', 'arguments': pie_data}
# → Generates pie chart with percentage labels on external leader lines
# → Includes complete breakdown table with totals
```

## Technical Implementation

### Leader Line Algorithm (Circle Packing)

```javascript
// Calculate label position around perimeter
const angle = (i / sortedLeaves.length) * 2 * Math.PI;
const labelDistance = Math.max(d.r + 40, 60);
const labelX = d.x + Math.cos(angle) * labelDistance;
const labelY = d.y + Math.sin(angle) * labelDistance;

// Anchor point on circle edge
const anchorX = d.x + Math.cos(angle) * d.r;
const anchorY = d.y + Math.sin(angle) * d.r;

// Draw leader line from circle to label
labelGroup.append('line')
    .attr('x1', anchorX).attr('y1', anchorY)
    .attr('x2', labelX).attr('y2', labelY)
    .attr('stroke-dasharray', '2,2');
```

### Data Table Generation

```javascript
// Create responsive table below chart
const tableDiv = container.append('div')
    .style('margin-top', '30px')
    .style('padding', '20px')
    .style('background', '#f8f9fa');

const table = tableDiv.append('table')
    .style('width', '100%')
    .style('border-collapse', 'collapse');

// Add rows with alternating colors
tbody.append('tr')
    .style('background', i % 2 === 0 ? 'white' : '#ecf0f1')
    .append('td').html(`
        <span style="background:${color};width:12px;height:12px;..."></span>
        ${name}
    `);
```

## Best Practices

### For Circle Packing:
1. **Limit to 30-50 items** for readable labels
2. **Use contrasting colors** for portfolio grouping
3. **Include detailed info** in `details` object for table
4. **Filter zero values** before charting (better space utilization)

### For Pie Charts:
1. **Use 3-8 slices** for optimal readability
2. **Sort by value descending** for visual flow
3. **Use color-blind friendly palettes** (e.g., Tableau10)
4. **Include percentage in labels** for quick insights

### For Screenshots:
1. **Use viewport 1400×1200+** for high resolution
2. **Enable full_page=True** to capture table
3. **Wait 3000ms** for D3 animations to complete
4. **Save as PNG** for best PowerPoint compatibility

## File Structure

```
mcp-d3-stdio-custom/
├── d3_chart_api_server.py          # Core chart generator
│   ├── script_packed()              # ✨ Enhanced with labels
│   └── script_pie()                 # ✨ Enhanced with labels
├── d3_chart_mcp.py                  # MCP server wrapper
├── test_enhanced_circle_packing.py  # Test script
└── html-charts/
    ├── packed_TIMESTAMP.html        # Output with labels
    └── pie_TIMESTAMP.html           # Output with labels
```

## Future Enhancements

- [ ] Bar charts with value labels on top of bars
- [ ] Line charts with data point annotations
- [ ] Heatmap with cell value labels
- [ ] Configurable label font size and positioning
- [ ] CSV export of data table
- [ ] Label collision detection and auto-adjustment

## Testing

Run the test suite:

```bash
cd D:/SourceCode/GenAI/MCP/server/charts/mcp-d3-stdio-custom
python test_enhanced_circle_packing.py
```

Expected output:
```
✅ Chart generated successfully!
   File: html-charts/packed_20251120_182430_6b3d5a24.html
📊 Enhanced Features:
   ✓ Leader lines connecting labels to circles
   ✓ External data labels (visible in screenshots)
   ✓ Complete data table below chart
```

## Conclusion

With these enhancements, D3 charts are now **screenshot-ready** with all data visible without requiring interactive tooltips. Perfect for:

- 📊 **PowerPoint presentations**
- 📄 **Static reports (PDF)**
- 📧 **Email attachments**
- 🖼️ **Documentation**
- 📱 **Sharing on platforms without JavaScript support**

**No more lost data in screenshots!** 🎉
