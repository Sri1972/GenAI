"""
Simple example: Create a presentation using natural language

This script shows how easy it is to create presentations with the LLM client.
Just describe what you want in plain English!
"""

import asyncio
from ppt_llm_client import PowerPointLLMClient


async def create_sales_presentation():
    """Create a sales presentation using natural language"""
    
    # Initialize the client
    client = PowerPointLLMClient()
    await client.start_mcp_session()
    
    presentation_id = "sales_deck"
    
    print("\n🎯 Creating Sales Presentation using Natural Language...\n")
    
    # Request 1: Title slide
    await client.chat(
        "Create a presentation about Q4 Sales Results with a professional title slide",
        presentation_id
    )
    
    # Request 2: Key metrics dashboard
    await client.chat(
        "Add a metrics dashboard slide with 3 circular shapes showing: "
        "$5.2M revenue in green, 1.8M customers in blue, and 95% satisfaction in gold",
        presentation_id
    )
    
    # Request 3: Regional performance
    await client.chat(
        "Create a slide comparing regional sales with a bar chart: "
        "North $2M, South $1.5M, East $1M, West $700K",
        presentation_id
    )
    
    # Request 4: Team org chart
    await client.chat(
        "Add an organizational chart showing Sales VP at top, "
        "then 3 regional managers (North, South, East), "
        "and 6 sales reps at the bottom level. Use professional blue and green colors.",
        presentation_id
    )
    
    # Request 5: Sales process
    await client.chat(
        "Show our sales process with chevrons: "
        "Lead Generation → Qualification → Demo → Proposal → Close",
        presentation_id
    )
    
    # Request 6: Next steps
    await client.chat(
        "Add a final slide titled 'Next Steps' with bullet points: "
        "Hire 3 new reps, Expand to Midwest, Launch new product line, "
        "Increase marketing budget",
        presentation_id
    )
    
    # Save the presentation
    await client.save_presentation(presentation_id, "output/sales_deck.pptx")
    
    await client.close_mcp_session()
    
    print("\n✅ Presentation created successfully!")
    print("📁 File: output/sales_deck.pptx")
    print("\n" + "="*60)


async def create_quick_presentation():
    """Ultra-simple example - just one request"""
    
    client = PowerPointLLMClient()
    await client.start_mcp_session()
    
    # One simple request
    await client.chat(
        "Create a presentation about AI with a title slide and 3 slides showing "
        "benefits, challenges, and future trends with bullet points",
        "ai_presentation"
    )
    
    await client.save_presentation("ai_presentation", "output/ai_presentation.pptx")
    await client.close_mcp_session()
    
    print("\n✅ Quick presentation created!")


async def create_infographic_presentation():
    """Create an infographic-style presentation"""
    
    client = PowerPointLLMClient()
    await client.start_mcp_session()
    
    presentation_id = "infographic"
    
    # Title
    await client.chat(
        "Create a modern infographic presentation about 'Digital Transformation 2025'",
        presentation_id
    )
    
    # Stats dashboard
    await client.chat(
        "Add a statistics slide with 4 key numbers in large circles: "
        "67% companies adopted AI, $2.5T market size, 300% ROI average, 85% customer satisfaction. "
        "Use vibrant colors: purple, teal, orange, and green",
        presentation_id
    )
    
    # Timeline
    await client.chat(
        "Show a timeline of digital transformation from 2020 to 2025 with these milestones: "
        "2020 Cloud Migration, 2021 AI Integration, 2022 Automation, 2023 Data Analytics, "
        "2024 Customer Focus, 2025 Full Transformation",
        presentation_id
    )
    
    # Process cycle
    await client.chat(
        "Add a cycle diagram showing: Assess → Plan → Implement → Measure → Optimize",
        presentation_id
    )
    
    await client.save_presentation(presentation_id, "output/infographic.pptx")
    await client.close_mcp_session()
    
    print("\n✅ Infographic presentation created!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "quick":
            asyncio.run(create_quick_presentation())
        elif sys.argv[1] == "infographic":
            asyncio.run(create_infographic_presentation())
        else:
            print("Usage: python simple_example.py [quick|infographic]")
            print("Or run without arguments for full sales deck example")
    else:
        asyncio.run(create_sales_presentation())
