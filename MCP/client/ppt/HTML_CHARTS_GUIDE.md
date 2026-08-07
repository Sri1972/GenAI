# Adding HTML Charts to PowerPoint

## Overview

You have **3 methods** to add HTML charts to PowerPoint presentations:

1. **Screenshot Method** - Capture HTML as image → Add to PPT ⭐ **Best quality**
2. **LLM Analysis** - Extract data → Create native PPT charts
3. **Natural Language** - Describe chart → LLM creates similar visualization

---

## Method 1: Screenshot (Recommended) ⭐

### How It Works
1. Use Playwright to render HTML in a headless browser
2. Take a screenshot of the rendered chart
3. Add the image to PowerPoint using `add_image_slide`

### Pros
✅ **Preserves exact appearance** - Colors, fonts, interactivity visualization
✅ **Works with any HTML** - D3.js, Chart.js, Plotly, custom visualizations
✅ **High quality** - Vector-quality screenshots
✅ **Fast** - 2-3 seconds per chart

### Cons
❌ Not editable in PowerPoint (it's an image)
❌ Requires playwright installation

### Setup
```powershell
pip install playwright
playwright install chromium
```

### Usage
```python
from playwright.async_api import async_playwright

# Take screenshot
async with async_playwright() as p:
    browser = await p.chromium.launch()
    page = await browser.new_page(viewport={"width": 1200, "height": 800})
    await page.goto(f"file:///{html_file.as_posix()}")
    await page.wait_for_timeout(2000)  # Wait for D3.js/chart to render
    await page.screenshot(path="chart.png")
    await browser.close()

# Add to PowerPoint
client = PowerPointLLMClient()
await client.start_mcp_session()

result = await client.call_mcp_tool("add_image_slide", {
    "presentation_id": "my_deck",
    "title": "Project Portfolio Visualization",
    "image_path": "chart.png",
    "caption": "Circle packing showing project distribution"
})
```

### Example Output
✅ **pmo_with_chart.pptx** created with:
- Title slide
- Image slide with your D3.js circle packing chart
- Screenshot: `chart_screenshot.png`

---

## Method 2: LLM Analysis

### How It Works
1. Read the HTML file
2. Extract the data (JavaScript arrays, etc.)
3. Let LLM analyze and create native PowerPoint charts

### Pros
✅ **Editable in PowerPoint** - Native charts can be modified
✅ **Professional formatting** - PowerPoint's built-in styles
✅ **Data export** - Can export data from PPT charts

### Cons
❌ Loses custom styling
❌ Limited to PowerPoint chart types (bar, line, pie, column)
❌ Doesn't capture complex visualizations well

### Usage
```python
# Read HTML
html_content = Path("chart.html").read_text()

# Extract data (regex or parse)
import re
data_match = re.search(r'const data = \[(.*?)\];', html_content, re.DOTALL)

# Let LLM create native chart
await client.chat(
    f"""I have project data showing:
    - Time To Insight: $75,158
    - Fleet Intelligence: $24,720
    - Cloud 2.0: $22,901
    
    Create a bar chart showing top 5 projects by cost.""",
    "my_deck"
)
```

---

## Method 3: Natural Language (Fastest) ⚡

### How It Works
1. Describe the chart in natural language
2. LLM creates a similar visualization using PowerPoint tools

### Pros
✅ **Fastest** - No screenshot, no data extraction
✅ **Flexible** - LLM adapts to PowerPoint's capabilities
✅ **Good for summaries** - Focus on insights, not exact replication

### Cons
❌ Loses original design
❌ Approximate representation only
❌ May not capture all details

### Usage
```python
await client.chat(
    """I have a D3.js circle packing chart showing PMO projects.
    The chart has 4 portfolios with different colors:
    - Market & Sell (blue): Fleet Intelligence $24,720
    - Vehicles In Use (red): Cloud 2.0 $22,901  
    - Auto Insights (green): Time To Insight $75,158
    - Plan & Build (orange): Fast Forecast
    
    Create a slide summarizing this data.""",
    "my_deck"
)
```

### Example Output
✅ LLM created a **table slide** with:
- Portfolio names
- Top projects
- Values
- Status

---

## Comparison Table

| Feature | Screenshot | LLM Analysis | Natural Language |
|---------|-----------|--------------|------------------|
| **Quality** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Speed** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Editable** | ❌ | ✅ | ✅ |
| **Setup** | Playwright | None | None |
| **Best For** | D3.js, complex charts | Simple data charts | Quick summaries |

---

## Your HTML Chart Example

### Original Chart
```
File: D:\SourceCode\GenAI\MCP\client\pmo\html-charts\
      claude_answer_can_you_help_visualize_the_above_data_us_20251120_130358_264ce6.html
      
Type: D3.js Circle Packing Visualization
Data: 18 PMO projects across 4 portfolios
Dimensions: 900x600px
Interactive: Yes (tooltips, hover effects)
```

### Result with Method 1 (Screenshot)
```
✅ Created: output/pmo_with_chart.pptx
✅ Screenshot: output/chart_screenshot.png (1200x800px)
✅ Slides: 2 (Title + Chart image)
✅ Quality: Exact match of original
```

---

## Recommendations

### Use Screenshot (Method 1) When:
- ✅ Chart has custom styling/branding
- ✅ Using D3.js, Plotly, or complex libraries
- ✅ Need exact appearance preserved
- ✅ Chart is finalized (no edits needed)

### Use LLM Analysis (Method 2) When:
- ✅ Need editable charts in PowerPoint
- ✅ Data needs to be updated frequently
- ✅ Simple bar/line/pie charts
- ✅ Want PowerPoint's native styling

### Use Natural Language (Method 3) When:
- ✅ Quick prototype or draft
- ✅ Focus on insights, not exact visualization
- ✅ No access to original HTML file
- ✅ Creating multiple variations

---

## Advanced: Batch Processing

Process multiple HTML charts at once:

```python
async def add_multiple_charts():
    html_files = Path("html-charts").glob("*.html")
    
    client = PowerPointLLMClient()
    await client.start_mcp_session()
    
    await client.chat("Create a Portfolio Analysis deck", "portfolio")
    
    for html_file in html_files:
        # Screenshot each chart
        screenshot = await capture_html(html_file)
        
        # Add to presentation
        await client.call_mcp_tool("add_image_slide", {
            "presentation_id": "portfolio",
            "title": html_file.stem.replace("_", " ").title(),
            "image_path": str(screenshot)
        })
    
    await client.save_presentation("portfolio", "output/full_report.pptx")
    await client.close_mcp_session()
```

---

## Tips & Tricks

### 1. Adjust Screenshot Size
```python
page = await browser.new_page(viewport={"width": 1600, "height": 900})
```

### 2. Wait for Dynamic Content
```python
# Wait for specific element
await page.wait_for_selector("#chart svg")

# Or wait fixed time for complex animations
await page.wait_for_timeout(3000)
```

### 3. Screenshot Specific Element
```python
# Instead of full page, screenshot just the chart
chart_element = await page.query_selector("#chart")
await chart_element.screenshot(path="chart.png")
```

### 4. Optimize Image Size
```python
from PIL import Image

# Resize if needed
img = Image.open("chart.png")
img = img.resize((1200, 800), Image.LANCZOS)
img.save("chart_optimized.png", optimize=True, quality=90)
```

### 5. Combine Methods
```python
# Use screenshot for main chart
await add_screenshot(complex_d3_chart)

# Use native charts for simple data
await client.chat("Add a bar chart showing quarterly revenue", "deck")
```

---

## Troubleshooting

### Issue: Playwright Not Found
```powershell
pip install playwright
playwright install chromium
```

### Issue: Screenshot is Blank
- Increase wait time: `await page.wait_for_timeout(5000)`
- Check if chart uses external resources (CDN)
- Verify HTML file path is correct

### Issue: Chart Cut Off
- Increase viewport size
- Use `full_page=True` for full page screenshot
- Target specific element instead

### Issue: Low Resolution
- Increase viewport dimensions
- Use `scale=2` for retina quality:
```python
await page.screenshot(path="chart.png", scale=2)
```

---

## Summary

**For your D3.js circle packing chart:**

✅ **Method 1 (Screenshot)** worked perfectly!
- Captured the exact visualization
- Preserved colors, layout, styling
- Added to PowerPoint in 10 seconds
- Output: `pmo_with_chart.pptx`

**Next steps:**
1. Open `output/pmo_with_chart.pptx` to see the result
2. View `output/chart_screenshot.png` for the captured image
3. Use the example script for your other HTML charts

**Command to run:**
```powershell
cd d:\SourceCode\GenAI\MCP\client\ppt
python add_html_chart_example.py 1
```
