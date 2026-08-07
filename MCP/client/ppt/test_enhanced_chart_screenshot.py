"""
Test screenshot of enhanced D3 chart with data labels and leader lines.
"""
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

async def screenshot_enhanced_chart():
    """Take screenshot of the enhanced circle packing chart."""
    
    # Find the generated HTML file
    html_file = Path("D:/SourceCode/GenAI/MCP/server/charts/mcp-d3-stdio-custom/html-charts").glob("packed_*.html")
    html_files = sorted(html_file, key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not html_files:
        print("❌ No packed chart HTML files found")
        return
    
    latest_html = html_files[0]
    print(f"📄 Using HTML file: {latest_html.name}")
    
    # Take screenshot
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 1200})
        
        await page.goto(f"file:///{latest_html}")
        
        # Wait for D3 to render
        await page.wait_for_timeout(3000)
        
        # Take full page screenshot
        output_path = Path("output/enhanced_chart_with_labels.png")
        output_path.parent.mkdir(exist_ok=True)
        
        await page.screenshot(path=str(output_path), full_page=True)
        
        await browser.close()
        
        print(f"✅ Screenshot saved: {output_path}")
        print(f"   Size: {output_path.stat().st_size / 1024:.1f} KB")
        print(f"\n💡 The screenshot should now show:")
        print(f"   ✓ Leader lines from circles to labels")
        print(f"   ✓ External data labels (Name: Value)")
        print(f"   ✓ Complete data table below the chart")
        print(f"   → ALL data is visible even without interactivity!")

if __name__ == "__main__":
    asyncio.run(screenshot_enhanced_chart())
