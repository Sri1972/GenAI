"""
Example: Add HTML chart to PowerPoint presentation

This demonstrates two approaches:
1. Screenshot HTML chart and add as image
2. Extract data and recreate native PowerPoint chart
"""

import asyncio
from ppt_llm_client import PowerPointLLMClient
from pathlib import Path


async def add_html_chart_as_screenshot():
    """
    Approach 1: Convert HTML to image using Playwright/Selenium
    Then add the image to PowerPoint
    """
    print("\n🎨 Method 1: Screenshot HTML Chart → Add to PowerPoint\n")
    
    # First, we need to install playwright
    print("Installing playwright (one-time setup)...")
    import subprocess
    subprocess.run(["pip", "install", "playwright"], capture_output=True)
    subprocess.run(["playwright", "install", "chromium"], capture_output=True)
    
    from playwright.async_api import async_playwright
    
    html_file = Path(r"D:\SourceCode\GenAI\MCP\client\pmo\html-charts\claude_answer_can_you_help_visualize_the_above_data_us_20251120_130358_264ce6.html")
    screenshot_path = Path(r"D:\SourceCode\GenAI\MCP\client\ppt\output\chart_screenshot.png")
    
    # Take screenshot of HTML chart
    print(f"📸 Taking screenshot of: {html_file.name}")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1400, "height": 1000})
        
        # Load the HTML file
        await page.goto(f"file:///{html_file.as_posix()}")
        
        # Wait for chart to render (D3.js needs time)
        await page.wait_for_timeout(3000)
        
        # Take full page screenshot to capture everything
        await page.screenshot(path=screenshot_path, full_page=True)
        await browser.close()
    
    print(f"✅ Screenshot saved: {screenshot_path}\n")
    
    # Add to PowerPoint
    client = PowerPointLLMClient()
    await client.start_mcp_session()
    
    presentation_id = "pmo_report"
    
    # Create presentation
    await client.chat(
        "Create a presentation titled 'PMO Project Portfolio Report'",
        presentation_id
    )
    
    # Add the chart as an image
    print("📊 Adding chart to PowerPoint...")
    result = await client.call_mcp_tool("add_image_slide", {
        "presentation_id": presentation_id,
        "title": "PMO Project Portfolio - Circle Packing Visualization",
        "image_path": str(screenshot_path),
        "caption": "Project distribution by portfolio and planned cost"
    })
    print(f"✅ {result}")
    
    # Save presentation
    await client.save_presentation(presentation_id, "output/pmo_with_chart_full.pptx")
    await client.close_mcp_session()
    
    print("\n✅ Presentation created: output/pmo_with_chart_full.pptx")


async def add_html_chart_with_llm():
    """
    Approach 2: Let the LLM analyze the HTML and decide how to present it
    """
    print("\n🤖 Method 2: LLM Analyzes HTML → Creates Presentation\n")
    
    html_file = Path(r"D:\SourceCode\GenAI\MCP\client\pmo\html-charts\claude_answer_can_you_help_visualize_the_above_data_us_20251120_130358_264ce6.html")
    
    # Read the HTML content
    html_content = html_file.read_text(encoding='utf-8')
    
    # Extract just the data part (lines 200-220 approximately)
    import re
    data_match = re.search(r'const projectData = \[(.*?)\];', html_content, re.DOTALL)
    
    if data_match:
        data_str = data_match.group(1)
        print(f"📊 Found project data in HTML\n")
    
    client = PowerPointLLMClient()
    await client.start_mcp_session()
    
    presentation_id = "pmo_analysis"
    
    # Let the LLM analyze and create slides
    await client.chat(
        "Create a PMO Portfolio Report presentation with title slide",
        presentation_id
    )
    
    # Provide the data and let LLM decide visualization
    await client.chat(
        f"""The HTML chart shows PMO project data with these portfolios:
        - Market & Sell (blue) - includes Blade Runner, Concord, Fleet Intelligence projects
        - Vehicles In Use (red) - includes Cloud 2.0, VIN Solutions projects  
        - Auto Insights (green) - includes Time To Insight, NITRO Development
        - Plan & Build (orange) - includes Fast Forecast projects
        
        Create a slide showing the top 5 projects by planned cost with a bar chart.
        The largest projects are:
        - Time To Insight: $75,158
        - Fleet Intelligence: $24,720
        - Blade Runner VIN Solutions: $25,027
        - Concept Memo: $25,286
        - Cloud 2.0: $22,901
        """,
        presentation_id
    )
    
    # Add portfolio summary
    await client.chat(
        """Add a slide with a dashboard showing portfolio statistics using circular shapes:
        - Market & Sell: 4 active projects in blue
        - Vehicles In Use: 3 active projects in red
        - Auto Insights: 3 active projects in green
        - Plan & Build: 1 active project in orange
        """,
        presentation_id
    )
    
    await client.save_presentation(presentation_id, "output/pmo_analysis.pptx")
    await client.close_mcp_session()
    
    print("\n✅ Presentation created: output/pmo_analysis.pptx")


async def quick_add_chart():
    """
    Quickest method: Just tell the LLM you have an HTML chart
    """
    print("\n⚡ Method 3: Natural Language - Tell LLM about the chart\n")
    
    client = PowerPointLLMClient()
    await client.start_mcp_session()
    
    await client.chat(
        """Create a presentation about our PMO Portfolio. 
        I have a D3.js circle packing visualization showing project distribution.
        The chart shows 4 portfolios with different colors:
        - Market & Sell (blue) with projects like Fleet Intelligence ($24,720) and Blade Runner
        - Vehicles In Use (red) with Cloud 2.0 ($22,901) and VIN Solutions  
        - Auto Insights (green) with Time To Insight ($75,158) - our largest project
        - Plan & Build (orange) with Fast Forecast
        
        Create a title slide and a summary slide showing the top projects.""",
        "pmo_quick"
    )
    
    await client.save_presentation("pmo_quick", "output/pmo_quick.pptx")
    await client.close_mcp_session()
    
    print("\n✅ Presentation created: output/pmo_quick.pptx")


if __name__ == "__main__":
    import sys
    
    print("\n" + "="*60)
    print("Add HTML Chart to PowerPoint - Demo")
    print("="*60)
    print("\nChoose a method:")
    print("1. Screenshot HTML → Image in PPT (requires playwright)")
    print("2. LLM analyzes data → Native PPT charts")
    print("3. Quick: Natural language description (fastest)")
    print("="*60 + "\n")
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("Enter choice (1-3): ")
    
    if choice == "1":
        asyncio.run(add_html_chart_as_screenshot())
    elif choice == "2":
        asyncio.run(add_html_chart_with_llm())
    elif choice == "3":
        asyncio.run(quick_add_chart())
    else:
        print("Invalid choice")
