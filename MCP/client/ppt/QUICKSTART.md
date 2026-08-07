# Quick Start Guide

## TL;DR - Get Started in 2 Minutes

### 1. Install & Setup
```powershell
# Install dependencies
pip install -r requirements.txt

# .env file is already configured
# Default provider: Bedrock (AWS)
# Available: bedrock, anthropic, openai, gemini
```

### 2. Run Interactive Mode
```powershell
cd d:\SourceCode\GenAI\MCP\client\ppt
python ppt_llm_client.py
```

### 3. Create Presentations with Natural Language
```
💬 You: Create a presentation about Q4 results

💬 You: Add a metrics dashboard with our KPIs

💬 You: save
```

Done! That's it! 🎉

---

## LLM Providers

The client supports **4 LLM providers** configured in `.env`:

| Provider | Model | Use Case |
|----------|-------|----------|
| **Bedrock** (default) | Claude Sonnet 4 | Enterprise, AWS integrated |
| **Anthropic** | Claude 3 Sonnet | Direct API access |
| **OpenAI** | GPT-4 | Widely compatible |
| **Gemini** | Gemini 1.5 Pro | Google ecosystem |

**To switch providers**, edit `.env`:
```bash
LLM_PROVIDER=bedrock  # Change to: anthropic, openai, or gemini
```

**Or specify in code:**
```python
client = PowerPointLLMClient(provider="openai")
```

---

## Simple Example

Create `my_first_presentation.py`:

```python
import asyncio
from ppt_llm_client import PowerPointLLMClient

async def main():
    client = PowerPointLLMClient()
    await client.start_mcp_session()
    
    # Just describe what you want!
    await client.chat(
        "Create a presentation about our company with a title slide "
        "and 3 slides showing our mission, vision, and values",
        "company_intro"
    )
    
    await client.save_presentation("company_intro", "output/company.pptx")
    await client.close_mcp_session()

asyncio.run(main())
```

Run it:
```powershell
python my_first_presentation.py
```

---

## What Can You Create?

### Simple Requests ✨
```
"Create a sales presentation"
"Add a title slide"
"Show our team structure"
```

### Metrics & Dashboards 📊
```
"Add a KPI dashboard with 4 metrics in circles"
"Show revenue: $5M, users: 1.2M, satisfaction: 95%"
```

### Org Charts 👥
```
"Create an org chart with CEO and 3 departments"
"Show reporting structure with 10 people"
```

### Process Flows ➡️
```
"Show customer journey: Awareness → Interest → Purchase"
"Add sales process with 5 stages"
```

### Custom Layouts 🎨
```
"Create a timeline from Jan to Dec"
"Add a pyramid with 5 levels"
"Show a cycle diagram with 4 steps"
```

---

## Key Benefits

### For Users 👤
- **No coding required** - Just describe what you want
- **Natural language** - Talk to it like a human
- **Smart layouts** - AI figures out positioning and colors
- **Fast** - Create presentations in seconds

### For Developers 👨‍💻
- **Clean API** - Simple async interface
- **Extensible** - Add new tools easily
- **MCP protocol** - Standard interface
- **Type safe** - Full type hints

---

## Common Patterns

### Pattern 1: Sequential Slides
```python
await client.chat("Create a presentation", "deck")
await client.chat("Add title slide", "deck")
await client.chat("Add agenda", "deck")
await client.chat("Add content", "deck")
await client.save_presentation("deck", "output/deck.pptx")
```

### Pattern 2: Complete Request
```python
await client.chat(
    "Create a complete presentation about AI with title, "
    "3 content slides, and a conclusion",
    "ai_deck"
)
```

### Pattern 3: Interactive
```python
# Start session once
await client.start_mcp_session()

# Multiple interactions
while True:
    user_input = input("What do you want? ")
    await client.chat(user_input, "my_deck")
```

---

## Example Conversations

### Example 1: Sales Deck
```
You: Create a sales presentation for Q4
AI: ✓ Created presentation with title slide

You: Add our top 3 achievements with big numbers
AI: ✓ Added metrics slide with 3 circular shapes

You: Show revenue growth chart
AI: ✓ Added bar chart comparing quarters

You: Add team org chart
AI: ✓ Created hierarchical org chart with 9 shapes

You: save
AI: ✓ Saved to output/sales_deck.pptx
```

### Example 2: Product Launch
```
You: Create a product launch presentation
AI: ✓ Created presentation

You: Add a timeline showing development from Jan to Jun
AI: ✓ Added timeline slide with 6 events

You: Show the 4 key features in a grid
AI: ✓ Added slide with 4 shapes in 2x2 grid

You: Add pricing table comparing 3 tiers
AI: ✓ Added table slide

You: save
```

---

## Tips & Tricks

### Be Specific About Colors
```
❌ "make it pretty"
✅ "use blue for headers, green for positive metrics"
```

### Describe Layout
```
❌ "add some shapes"
✅ "add 3 circles at the top, evenly spaced"
```

### Use Numbers
```
❌ "show the team"
✅ "show org chart with 1 CEO, 3 VPs, 6 managers"
```

### Mention Style
```
❌ "add metrics"
✅ "add a dashboard-style metrics slide with large numbers"
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Provider error | Check `.env` has correct API keys/credentials |
| Bedrock auth error | Verify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY |
| Anthropic error | Check ANTHROPIC_API_KEY in `.env` |
| OpenAI error | Check OPENAI_API_KEY in `.env` |
| Gemini error | Check GEMINI_API_KEY in `.env` |
| MCP not starting | Check server path in line 173 |
| Empty slides | Update MSO_SHAPE constants (see main README) |
| Import errors | Run `pip install -r requirements.txt` |

---

## Next Steps

1. ✅ Try the interactive mode
2. ✅ Run `simple_example.py`
3. ✅ Create your own requests
4. ✅ Read full README for advanced features
5. ✅ Customize system prompt for your needs

---

## Need Help?

- 📖 Full docs: `README.md`
- 🎨 Shape guide: `../../server/ppt/CUSTOM_SHAPES_GUIDE.md`
- 🔧 Server docs: `../../server/ppt/README.md`
- 💡 Examples: `simple_example.py`

---

**That's it! Start creating presentations with natural language! 🚀**
