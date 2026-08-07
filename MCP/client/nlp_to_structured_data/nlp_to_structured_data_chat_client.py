#!/usr/bin/env python3
"""
Unified Data Chat Client - Clean Architecture

Based on the proven test_clean_server.py approach, this client maintains
a single persistent MCP session for both data loading and querying.

Features:
- Single persistent session (no session management issues)
- LLM-powered intelligent responses  
- Mandatory metadata with auto-discovery
- Support for CSV, Excel, JSON files
- Interactive and single-message modes
- Direct service architecture (no agents)
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    # MCP imports
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("MCP not available. Install with: pip install mcp")
    sys.exit(1)

# Import LLM utilities  
from utils.llm_utils import ClaudeBedrockProvider, MockLLMProvider

class UnifiedDataChatClient:
    """Unified Data Chat Client with single persistent session."""
    
    def __init__(self, llm_provider: str = "claude", model_name: Optional[str] = None):
        # Configure MCP server connection
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).parent.parent.parent / "server" / "nlp_to_structured_data" / "nlp_to_structured_data_mcp_server.py")]
        )
        
        # Initialize LLM provider
        self.llm_provider_name = llm_provider
        self.llm = self._initialize_llm_provider(llm_provider, model_name)
        
        # State tracking
        self.data_loaded = False
        self.data_context = ""
        self.chat_history = []
        self.loaded_metadata = {}
        
    def _initialize_llm_provider(self, provider: str, model_name: Optional[str] = None):
        """Initialize the specified LLM provider."""
        try:
            if provider.lower() in ["claude", "bedrock"]:
                llm = ClaudeBedrockProvider()
                print(f"🤖 Initialized Claude Bedrock LLM")
                return llm
            elif provider.lower() == "mock":
                llm = MockLLMProvider()
                print(f"🤖 Initialized Mock LLM (for testing)")
                return llm
            else:
                print(f"⚠️ Unknown LLM provider: {provider}. Using Claude Bedrock.")
                return ClaudeBedrockProvider()
                
        except Exception as e:
            print(f"⚠️ Failed to initialize {provider} LLM: {e}")
            print(f"🔄 Falling back to Mock LLM provider...")
            return MockLLMProvider()
    
    async def run_single_session_workflow(self, file_path: str = None, file_type: str = None, 
                                         metadata_file: str = None,
                                         query: str = None, interactive: bool = False, fast_mode: bool = False):
        """Run entire workflow in a single persistent MCP session."""
        try:
            print("🔗 Connecting to Clean Data MCP server...")
            async with stdio_client(self.server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    print("✅ MCP session ready")
                    
                    # Load data if provided (optional now - can load in chat)
                    if file_path and file_type and metadata_file:
                        await self._load_file_data(session, file_path, file_type, metadata_file)
                    # If no data provided and interactive mode, that's OK - user can load in chat
                    elif not interactive and not query:
                        print("❌ No data source specified. Use --file with --type, or --interactive")
                        return False
                    
                    # Handle different modes
                    if interactive:
                        await self._interactive_mode(session, fast_mode)
                    elif query:
                        if not self.data_loaded:
                            print("❌ Cannot execute query: No data loaded. Use --file with --type to load data first.")
                            return False
                        await self._single_query(session, query, skip_llm=fast_mode)
                    else:
                        print("✅ Data loaded successfully! Use --interactive or --message for queries.")
                        return True
                        
                    return True
        
        except KeyboardInterrupt:
            print("\n👋 Exiting gracefully...")
            return True
        except Exception as e:
            print(f"❌ Session error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _load_file_data(self, session, file_path: str, file_type: str, metadata_file: str):
        """Load file data in the current session."""
        print(f"📂 Loading {file_type.upper()} file: {file_path}")
        print(f"📋 Loading metadata: {metadata_file}")
        
        # Load metadata locally for LLM context
        if Path(metadata_file).exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                self.loaded_metadata = json.load(f)
        
        # Load data via MCP
        result = await session.call_tool("load_data", {
            "file_path": file_path,
            "file_type": file_type,
            "metadata_path": metadata_file
        })
        
        if result and hasattr(result, 'content') and result.content:
            print(result.content[0].text)
            self.data_loaded = True
            file_desc = self.loaded_metadata.get('file_info', {}).get('description', 'Data file')
            self.data_context = f"Loaded: {file_type.upper()} file '{file_path}' - {file_desc}"
        else:
            print("❌ Failed to load file data")
    
    async def _single_query(self, session, query: str, skip_llm: bool = False):
        """Execute a single query in the current session."""
        if not self.data_loaded:
            print("❌ No data loaded for query")
            return
            
        print(f"🔍 Executing query: {query}")
        
        # Get direct server analysis (always fast)
        direct_result = await session.call_tool("intelligent_query", {
            "query": query,
            "format_style": "clear analysis",
            "use_agent_intelligence": False
        })
        
        server_analysis = ""
        if direct_result and hasattr(direct_result, 'content') and direct_result.content:
            server_analysis = direct_result.content[0].text
        
        print(f"\n📊 Server Analysis:")
        if server_analysis.startswith("ERROR:"):
            print(f"⚠️ {server_analysis}")
            print(f"\n💡 The server encountered an issue analyzing the data.")
            print(f"   This could be due to:")
            print(f"   • Data type mismatches (dates stored as text, numbers as strings)")
            print(f"   • Column name variations not matching expected format")
            print(f"   • Missing or malformed data in key columns")
            print(f"   • File encoding or formatting issues")
        else:
            print(server_analysis)
        
        # Optional LLM enhancement (can be slow)
        if not skip_llm and self.llm_provider_name != "none":
            print(f"🤖 Enhancing with {self.llm_provider_name} LLM... (this may take a moment)")
            
            try:
                # Create focused prompt for faster processing
                business_context = ""
                if self.loaded_metadata:
                    file_info = self.loaded_metadata.get('file_info', {})
                    business_context = f"Context: {file_info.get('description', 'Data analysis')}"
                
                # Check if server analysis contains errors
                has_server_error = server_analysis.startswith("ERROR:")
                
                if has_server_error:
                    # More detailed prompt for error scenarios
                    focused_prompt = f"""Data Analysis Issue Resolution:

{business_context}
{self.data_context}

Server Error: {server_analysis}

User Query: {query}

The data analysis server encountered an error. Based on the error message and the user's query, please:

1. **Identify the likely cause** of the error (data type issues, column names, etc.)
2. **Suggest specific solutions** to fix the data or query approach
3. **Provide alternative analysis approaches** that might work around the issue
4. **Give business insights** if possible based on the error context

Be practical and actionable in your response."""
                else:
                    # Standard enhancement prompt
                    focused_prompt = f"""Data Analysis Enhancement:

{business_context}
{self.data_context}

Server found: {server_analysis}

User asked: {query}

Provide 2-3 key business insights and recommendations based on this analysis. Be concise and actionable."""
                
                # Add timeout for LLM call
                enhanced_response = await asyncio.wait_for(
                    self.llm.generate_response(focused_prompt),
                    timeout=15.0  # 15 second timeout
                )
                
                print(f"\n🎯 Enhanced Insights:")
                print(enhanced_response)
                
                # Update chat history
                self.chat_history.append({
                    "user": query,
                    "server_analysis": server_analysis,
                    "enhanced_response": enhanced_response
                })
                
            except asyncio.TimeoutError:
                print(f"⏰ LLM enhancement timed out (>15s). Server analysis above is complete.")
                self.chat_history.append({
                    "user": query,
                    "server_analysis": server_analysis,
                    "enhanced_response": "LLM enhancement timed out"
                })
            except Exception as e:
                print(f"⚠️ LLM enhancement failed ({e}). Server analysis above is complete.")
                self.chat_history.append({
                    "user": query,
                    "server_analysis": server_analysis,
                    "enhanced_response": f"LLM error: {e}"
                })
        else:
            # Just use server analysis
            self.chat_history.append({
                "user": query,
                "server_analysis": server_analysis,
                "enhanced_response": "Server analysis only"
            })
    
    async def _interactive_mode(self, session, fast_mode: bool = False):
        """Interactive chat mode with in-session data loading commands."""
        mode_desc = "⚡ FAST MODE (server analysis only)" if fast_mode else f"🤖 Enhanced mode with {self.llm_provider_name} LLM"
        data_status = self.data_context if self.data_loaded else "❌ No data loaded yet"
        
        print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  🚀 Unified Data Chat Client - Interactive Mode                  ║
║  {mode_desc:<62} ║
║  📊 Data: {data_status:<53} ║
╚══════════════════════════════════════════════════════════════════╝

📂 Data Loading Commands:
  /load                           - Interactive data loading (prompts for details)
  /load <file> <type> [metadata]  - Load file directly
    Example: /load D:/data/sales.csv csv D:/data/sales.metadata.json
    Example: /load D:/reports/data.xlsx excel
  /reload                         - Reload current data source
  /status                         - Show current data loading status

💬 Chat Commands:
  /fast                           - Toggle fast mode (⚡ server-only vs 🤖 LLM-enhanced)
  /context                        - Show current data context
  /history                        - Show recent chat history
  /clear                          - Clear chat history
  /aliases                        - Show available column aliases (if metadata loaded)
  /help                           - Show this help message
  /quit or /exit                  - Exit the chat

💡 Tips:
  - Type /load to interactively load your data
  - Use full paths for data files (e.g., D:/SourceCode/GenAI/data.csv)
  - Then ask questions about your data in natural language
  - Use /fast to switch between quick analysis and detailed insights

Ask away!
        """)

        current_fast_mode = fast_mode
        last_load_command = None  # Track for reload

        while True:
            try:
                mode_indicator = "⚡" if current_fast_mode else "🤖"
                data_indicator = "✓" if self.data_loaded else "✗"
                
                try:
                    user_input = input(f"\n{mode_indicator}[{data_indicator}] You: ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\n👋 Goodbye!")
                    break

                if not user_input:
                    continue

                # Handle commands (start with /)
                if user_input.startswith('/'):
                    command_parts = user_input[1:].split()
                    command = command_parts[0].lower()

                    # Exit commands
                    if command in ['quit', 'exit', 'q']:
                        print("👋 Goodbye!")
                        break

                    # Toggle fast mode
                    elif command == 'fast':
                        current_fast_mode = not current_fast_mode
                        mode_desc = "⚡ FAST MODE (server analysis only)" if current_fast_mode else f"🤖 Enhanced mode with {self.llm_provider_name} LLM"
                        print(f"🔄 Switched to: {mode_desc}")
                        continue

                    # Clear history
                    elif command == 'clear':
                        self.chat_history = []
                        print("🧹 Chat history cleared.")
                        continue

                    # Show context
                    elif command == 'context':
                        if self.data_loaded:
                            print(f"📊 Current context: {self.data_context}")
                            if self.loaded_metadata:
                                file_info = self.loaded_metadata.get('file_info', {})
                                print(f"   Description: {file_info.get('description', 'N/A')}")
                                print(f"   Columns: {len(self.loaded_metadata.get('columns', {}))}")
                        else:
                            print("❌ No data loaded. Use /load to load data.")
                        continue

                    # Show history
                    elif command == 'history':
                        if self.chat_history:
                            print("📜 Chat History (last 5):")
                            for i, entry in enumerate(self.chat_history[-5:], 1):
                                print(f"  {i}. Q: {entry['user'][:60]}...")
                        else:
                            print("📜 No chat history yet")
                        continue

                    # Show column aliases
                    elif command == 'aliases':
                        if not self.data_loaded:
                            print("❌ No data loaded. Load data first to see available column aliases.")
                        else:
                            print("📋 Fetching column aliases...")
                            try:
                                aliases_result = await session.call_tool("list_column_aliases", {})
                                if aliases_result and hasattr(aliases_result, 'content') and aliases_result.content:
                                    print(f"\n{aliases_result.content[0].text}")
                                else:
                                    print("❌ Failed to retrieve column aliases.")
                            except Exception as e:
                                print(f"❌ Error fetching aliases: {e}")
                        continue

                    # Show status
                    elif command == 'status':
                        status = "✅ Data loaded" if self.data_loaded else "❌ No data loaded"
                        print(f"📊 Status: {status}")
                        if self.data_loaded:
                            print(f"   Context: {self.data_context}")
                        print(f"   Mode: {'⚡ Fast' if current_fast_mode else '🤖 Enhanced'}")
                        print(f"   LLM: {self.llm_provider_name}")
                        print(f"   History: {len(self.chat_history)} entries")
                        continue

                    # Show help
                    elif command == 'help':
                        print("""
📖 Available Commands:

Data Loading:
  /load                           - Interactive data loading (prompts for all details)
  /load <file> <type> [metadata]  - Load data file directly
    Example: /load D:/data/sales.csv csv D:/data/sales.metadata.json
    Example: /load D:/reports/data.xlsx excel
  /reload                         - Reload the last data source
  /status                         - Show current status

Chat:
  /fast                           - Toggle fast/enhanced mode
  /context                        - Show data context
  /history                        - Show chat history
  /clear                          - Clear chat history
  /aliases                        - Show column aliases (if metadata loaded)
  /help                           - Show this help
  /quit or /exit                  - Exit

💡 Tip: Type /load to interactively load your data file!
                        """)
                        continue

                    # Load file command: /load [<file> <type> [metadata]]
                    elif command == 'load':
                        # Interactive mode if no parameters or just "load data"
                        if len(command_parts) == 1 or (len(command_parts) == 2 and command_parts[1].lower() == 'data'):
                            print("\n📂 Interactive Data Loading")
                            print("=" * 60)
                            
                            # Ask for file path
                            try:
                                file_path = input("Enter data file path (full path): ").strip()
                                if not file_path:
                                    print("❌ File path cannot be empty.")
                                    continue
                                
                                # Check if file exists
                                if not Path(file_path).exists():
                                    print(f"❌ File not found: {file_path}")
                                    continue
                                
                                # Ask for file type
                                print("\nAvailable file types: csv, excel, json")
                                file_type = input("Enter file type: ").strip().lower()
                                if file_type not in ['csv', 'excel', 'json']:
                                    print(f"❌ Invalid file type: {file_type}. Must be csv, excel, or json")
                                    continue
                                
                                # Ask for metadata path (optional)
                                print("\nMetadata file path (press Enter to auto-discover or skip):")
                                metadata_file = input("Enter metadata file path: ").strip()
                                
                                # Auto-discover if empty
                                if not metadata_file:
                                    file_stem = Path(file_path).stem
                                    auto_metadata = f"metadata/{file_type}/{file_stem}.metadata.json"
                                    if Path(auto_metadata).exists():
                                        metadata_file = auto_metadata
                                        print(f"✓ Auto-discovered metadata: {metadata_file}")
                                    else:
                                        # Try alternate location
                                        alt_metadata = str(Path(file_path).with_suffix('')) + '.metadata.json'
                                        if Path(alt_metadata).exists():
                                            metadata_file = alt_metadata
                                            print(f"✓ Auto-discovered metadata: {metadata_file}")
                                
                                # Load the file
                                print(f"\n📊 Loading {file_type.upper()} file...")
                                await self._load_file_data(session, file_path, file_type, metadata_file or "")
                                last_load_command = ('file', file_path, file_type, metadata_file)
                                print(f"✅ Data loaded successfully! You can now ask questions about it.")
                                
                            except (KeyboardInterrupt, EOFError):
                                print("\n❌ Data loading cancelled.")
                                continue
                            except Exception as e:
                                print(f"❌ Failed to load file: {e}")
                                continue
                        
                        # Direct mode with parameters
                        elif len(command_parts) >= 3:
                            file_path = command_parts[1]
                            file_type = command_parts[2].lower()
                            metadata_file = command_parts[3] if len(command_parts) > 3 else None

                            # Validate file type
                            if file_type not in ['csv', 'excel', 'json']:
                                print(f"❌ Invalid file type: {file_type}. Use: csv, excel, or json")
                                continue

                            # Check if file exists
                            if not Path(file_path).exists():
                                print(f"❌ File not found: {file_path}")
                                continue

                            # Auto-discover metadata if not provided
                            if not metadata_file:
                                file_stem = Path(file_path).stem
                                auto_metadata = f"metadata/{file_type}/{file_stem}.metadata.json"
                                if Path(auto_metadata).exists():
                                    metadata_file = auto_metadata
                                    print(f"🔍 Auto-discovered metadata: {metadata_file}")
                                else:
                                    # Try alternate location
                                    alt_metadata = str(Path(file_path).with_suffix('')) + '.metadata.json'
                                    if Path(alt_metadata).exists():
                                        metadata_file = alt_metadata
                                        print(f"🔍 Auto-discovered metadata: {metadata_file}")

                            # Load the file
                            try:
                                await self._load_file_data(session, file_path, file_type, metadata_file or "")
                                last_load_command = ('file', file_path, file_type, metadata_file)
                                print(f"✅ Data loaded successfully! You can now ask questions about it.")
                            except Exception as e:
                                print(f"❌ Failed to load file: {e}")
                        
                        else:
                            print("❌ Usage: /load [<file> <type> [metadata]]")
                            print("   Or just type: /load (for interactive prompts)")
                            print("   Example: /load D:/data/sales.csv csv")
                        continue

                    # Reload command
                    elif command == 'reload':
                        if not last_load_command:
                            print("❌ No previous data to reload. Use /load first.")
                            continue

                        print("🔄 Reloading data...")
                        try:
                            _, file_path, file_type, metadata_file = last_load_command
                            await self._load_file_data(session, file_path, file_type, metadata_file or "")
                            print(f"✅ Data reloaded successfully!")
                        except Exception as e:
                            print(f"❌ Failed to reload: {e}")
                        continue

                    # Unknown command
                    else:
                        print(f"❌ Unknown command: /{command}")
                        print("   Type /help for available commands")
                        continue

                # Regular query (not a command)
                else:
                    # Check if data is loaded
                    if not self.data_loaded:
                        print("⚠️ No data loaded yet! Please load data first:")
                        print("   • /load                  - Load your data file interactively")
                        print("   • /load <file> <type>    - Load your own file")
                        print("   • /help                  - See all commands")
                        continue

                    # Process the query
                    await self._single_query(session, user_input, skip_llm=current_fast_mode)

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()

    
    def _format_chat_history(self):
        """Format chat history for context."""
        if not self.chat_history:
            return "No previous conversation."
        
        formatted = []
        for entry in self.chat_history[-3:]:  # Last 3 exchanges
            formatted.append(f"User: {entry['user']}")
            formatted.append(f"Analysis: {entry['enhanced_response'][:150]}...")
        
        return "\n".join(formatted)


async def main():
    """Main entry point for the Unified Data Chat Client."""
    parser = argparse.ArgumentParser(
        description="Unified Data Chat Client - Interactive data analysis",
        epilog="""
Examples:
  # Start interactive chat (load data within chat using /load)
  python nlp_to_structured_data_chat_client.py --interactive
  
  # Load file and start chat
  python nlp_to_structured_data_chat_client.py --data_file D:/data/sales.csv --type csv --interactive
  
  # Single query with pre-loaded data
  python nlp_to_structured_data_chat_client.py --data_file D:/data/sales.csv --type csv --message "Show top customers"
  
  # Fast mode (server-only, no LLM)
  python nlp_to_structured_data_chat_client.py --data_file D:/data/hr.csv --type csv --fast --interactive
        """
    )
    
    # Data loading arguments (optional - can load in chat)
    parser.add_argument("--data_file", help="Path to data file (optional - can load in chat)")
    parser.add_argument("--type", choices=["csv", "excel", "json"], help="Data file type")
    parser.add_argument("--metadata_file", help="Path to metadata file (auto-discovered if not provided)")
    
    # LLM configuration arguments
    parser.add_argument("--llm", choices=["claude", "bedrock", "mock", "none"], 
                       default="claude", help="LLM provider to use ('none' for server-only)")
    parser.add_argument("--model", help="Specific model name")
    parser.add_argument("--fast", action="store_true", help="Fast mode: server analysis only (no LLM)")
    
    # Interaction mode arguments
    parser.add_argument("--interactive", "-i", action="store_true", 
                       help="Run in interactive chat mode (default if no message provided)")
    parser.add_argument("--message", "-m", help="Single message to send (requires data to be loaded)")
    
    args = parser.parse_args()
    
    # Create unified client
    client = UnifiedDataChatClient(args.llm, args.model)
    
    try:
        # Determine data source
        file_path = args.data_file
        file_type = args.type
        metadata_file = args.metadata_file

        # Auto-discover metadata if file specified without metadata
        if file_path and file_type and not metadata_file:
            auto_metadata = f"metadata/{file_type}/{Path(file_path).stem}.metadata.json"
            if Path(auto_metadata).exists():
                metadata_file = auto_metadata
                print(f"🔍 Auto-discovered metadata: {metadata_file}")

        # If message is provided, it's a single query mode (data must be loaded)
        if args.message:
            if not (file_path and file_type and metadata_file):
                print("❌ Error: --message requires data to be loaded")
                print("   Use --data_file with --type to load data")
                print("   Example: python nlp_to_structured_data_chat_client.py --data_file D:/data/sales.csv --type csv --message 'Show summary'")
                return 1
            
            success = await client.run_single_session_workflow(
                file_path=file_path,
                file_type=file_type,
                metadata_file=metadata_file,
                query=args.message,
                interactive=False,
                fast_mode=args.fast or args.llm == "none"
            )
            return 0 if success else 1
        
        # Default to interactive mode (can load data in chat or pre-load)
        if args.interactive or not args.message:
            if not (file_path and file_type and metadata_file):
                print("💡 Starting interactive chat mode without pre-loaded data.")
                print("   You can load data using commands like:")
                print("   • /load                  - Load data interactively")
                print("   • /load D:/data/sales.csv csv")
                print("   • Type /help for all commands\n")
            
            success = await client.run_single_session_workflow(
                file_path=file_path,
                file_type=file_type,
                metadata_file=metadata_file,
                interactive=True,
                fast_mode=args.fast or args.llm == "none"
            )
            return 0 if success else 1

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)