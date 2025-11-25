# 🚀 NLP to Structured Data - AI-Powered Data Analysis

**Transform your data conversations with Claude AI via Model Context Protocol**

Chat with CSV, Excel, JSON, and API data using natural language. No complex queries needed - just ask questions in plain English and get intelligent, formatted responses!

## ✨ Key Features

- 🗣️ **Natural Language Queries**: "Show me top 5 customers by revenue"
- 🎨 **Claude-Powered Formatting**: Beautiful tables, summaries, and insights
- 📊 **Multi-Format Support**: CSV, Excel, JSON, API endpoints
- 🧠 **Business Intelligence**: Context-aware analysis with metadata integration
- � **MCP Integration**: Works with Claude Desktop and CLI
- ⚡ **Quick Start**: Sample datasets included for immediate testing

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Try with sample data
python nlp_to_structured_data_mcp_client.py --sample sales

# Load your own data
python nlp_to_structured_data_mcp_client.py --file sales.csv --type csv

# Interactive mode
python nlp_to_structured_data_mcp_client.py --interactive
```

## 💬 Example Conversation

```
🔍 You: "Load sample sales data and show me top customers"

📊 Claude: Here are your top customers by revenue:

| Customer    | Revenue  | Industry   | Region |
|------------|----------|------------|--------|
| AI Solutions| $120,000 | Technology | North  |
| WebTech     | $85,000  | Digital    | South  |
| DataInc     | $75,000  | Analytics  | East   |

**Key Insights:** AI Solutions leads with 32% of total revenue. 
Strong tech sector concentration suggests expansion opportunities.
```

## 🏗️ System Architecture

```
Claude Desktop / CLI Client
         ↓ (MCP STDIO Protocol)
    MCP Server (Python)
         ↓ (Agent System)
CSV Agent | Excel Agent | JSON Agent | API Agent
         ↓ (Claude Integration)
    Intelligent Analysis & Formatting
```

**Core Components:**
- **MCP Client**: `nlp_to_structured_data_mcp_client.py` - Command-line interface
- **MCP Server**: `mcp_servers/nlp_to_structured_data_mcp_server.py` - STDIO protocol server
- **Specialized Agents**: Format-specific data processors (CSV, Excel, JSON, API)
- **Claude Integration**: AI-powered analysis and intelligent formatting

## 🔧 Claude Desktop Integration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nlp-structured-data": {
      "command": "python",
      "args": [
        "D:/GenAI/MCP/nlp_to_structured_data/mcp_servers/nlp_to_structured_data_mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "D:/GenAI/MCP/nlp_to_structured_data"
      }
    }
  }
}
```

Then restart Claude Desktop and use natural language to analyze your data!

## 📚 Complete Documentation

**📖 [View Full Documentation](docs/index.html)** - Open in your browser for:

- **[📖 Complete System Guide](docs/index.html)** - Architecture, setup, and comprehensive usage
- **[🔌 MCP Integration Guide](docs/mcp-integration.html)** - Claude Desktop setup and protocol details  
- **[🤖 Agent Deep Dive](docs/agent-deep-dive.html)** - How CSV, Excel, JSON, and API agents work
- **[💡 Usage Examples](docs/examples.html)** - Real conversations and advanced workflows

*The HTML documentation provides interactive navigation, code examples, and detailed explanations of every system component.*

## 🎯 Supported Data Formats

| Format | Extension | Features |
|--------|-----------|----------|
| **CSV** | `.csv` | Headers, delimiters, encoding detection |
| **Excel** | `.xlsx`, `.xls` | Multiple sheets, formulas |
| **JSON** | `.json` | Nested objects, auto-flattening |
| **API** | REST endpoints | Pagination, authentication |

## ⚡ Environment Setup

1. **Install Requirements**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Claude Access** (create `.env` file):
   ```env
   # For Claude Bedrock (recommended)
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_DEFAULT_REGION=us-east-1
   
   # For Claude API (alternative)
   ANTHROPIC_API_KEY=your_anthropic_key
   ```

3. **Test Installation**:
   ```bash
   python nlp_to_structured_data_mcp_client.py --sample sales --query "Show me a summary"
   ```

## 🚀 What Makes This Special

### 🧠 **Intelligent, Not Hardcoded**
Unlike traditional data tools with rigid formatting, this system uses Claude's natural language understanding to format data exactly how you want it - in real-time, contextually.

### 🔗 **Metadata-Aware Business Intelligence**
Load `.metadata.json` files alongside your data to provide business context, column descriptions, and validation rules for smarter analysis.

### 🎨 **Adaptive Formatting**
Ask for data "as an executive dashboard", "as bullet points", or "with trend analysis" - Claude adapts the presentation to your needs.

### 🔌 **Modern MCP Architecture**
Built on Model Context Protocol for clean separation between data processing and AI interaction, enabling both CLI and Claude Desktop usage.

## 📄 License

MIT License - see LICENSE file for details.

---

**Ready to revolutionize how you analyze data?** 
**[📖 Start with the Complete Documentation](docs/index.html)** 🚀