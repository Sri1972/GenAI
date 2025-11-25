"""
PowerPoint MCP Client with LLM Intelligence

This client allows natural language interaction with the PowerPoint MCP server.
The LLM handles all the complexity of:
- Interpreting user requests
- Choosing appropriate shapes and layouts
- Determining colors, sizes, and positioning
- Structuring data for MCP tool calls
"""

import asyncio
import json
from typing import Optional, List, Dict, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import LLM providers based on configuration
try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai
except ImportError:
    openai = None

try:
    import boto3
except ImportError:
    boto3 = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None


class PowerPointLLMClient:
    """LLM-powered client for PowerPoint MCP server"""
    
    def __init__(self, provider: Optional[str] = None):
        """Initialize the client with specified LLM provider"""
        self.provider = provider or os.getenv("LLM_PROVIDER", "bedrock").lower()
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4096"))
        self.conversation_history = []
        self.mcp_session = None
        self.mcp_read = None
        self.mcp_write = None
        self.stdio_context = None
        self.session_context = None
        
        # Initialize the appropriate LLM client
        if self.provider == "anthropic":
            if anthropic is None:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            self.anthropic_client = anthropic.Anthropic(api_key=api_key)
            self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
            
        elif self.provider == "openai":
            if openai is None:
                raise ImportError("openai package not installed. Run: pip install openai")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            self.openai_client = openai.OpenAI(api_key=api_key)
            self.model = os.getenv("OPENAI_MODEL", "gpt-4")
            base_url = os.getenv("OPENAI_BASE_URL")
            if base_url:
                self.openai_client.base_url = base_url
                
        elif self.provider == "bedrock":
            if boto3 is None:
                raise ImportError("boto3 package not installed. Run: pip install boto3")
            
            # Get AWS credentials
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_region = os.getenv("AWS_REGION", "us-east-1")
            
            if aws_access_key and aws_secret_key:
                self.bedrock_client = boto3.client(
                    "bedrock-runtime",
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
            else:
                # Use default credentials (IAM role, AWS CLI config, etc.)
                self.bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=aws_region
                )
            
            self.model = os.getenv("BEDROCK_MODEL", "global.anthropic.claude-sonnet-4-20250514-v1:0")
            self.bedrock_anthropic_version = os.getenv("BEDROCK_ANTHROPIC_VERSION", "claude-sonnet-4-20250514-v1")
            
        elif self.provider == "gemini":
            if genai is None:
                raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in environment variables")
            genai.configure(api_key=api_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
            self.gemini_model = genai.GenerativeModel(model_name)
            self.model = model_name
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}. Choose from: anthropic, openai, bedrock, gemini")
        
        print(f"✓ Initialized {self.provider.upper()} client with model: {self.model}")
        
        # Available MCP tools documentation for the LLM
        self.tools_documentation = """
# PowerPoint MCP Server Tools

## Available Tools:

1. **create_presentation**
   - Creates a new PowerPoint presentation
   - Parameters: presentation_id (string)

2. **add_title_slide**
   - Adds a title slide
   - Parameters: presentation_id, title, subtitle (optional)

3. **add_content_slide**
   - Adds a slide with title and bullet points
   - Parameters: presentation_id, title, content (array of strings)

4. **add_two_column_slide**
   - Adds a slide with two columns
   - Parameters: presentation_id, title, left_content (array), right_content (array)

5. **add_image_slide**
   - Adds a slide with an image
   - Parameters: presentation_id, title, image_path, caption (optional)

6. **add_chart_slide**
   - Adds a slide with a chart
   - Parameters: presentation_id, title, chart_type ("bar", "column", "line", "pie"), 
     categories (array), series (array of {name, values})

7. **add_table_slide**
   - Adds a slide with a table
   - Parameters: presentation_id, title, headers (array), rows (array of arrays)

8. **add_process_flow_slide**
   - Adds a slide with chevron/arrow process flow
   - Parameters: presentation_id, title, steps (array of strings), 
     orientation ("horizontal" or "vertical")

9. **add_timeline_slide**
   - Adds a timeline slide with events
   - Parameters: presentation_id, title, events (array of {date, event})

10. **add_diagram_slide**
    - Adds various diagram types (cycle, pyramid, matrix)
    - Parameters: presentation_id, title, diagram_type ("cycle", "pyramid", "matrix"),
      items (array of strings, 3-4 items)

11. **add_shape_slide**
    - Adds a slide with custom shapes
    - Parameters: presentation_id, title, shapes (array of shape objects)
    - Shape object properties:
      * shape_type: "circle", "square", "rectangle", "rounded_rectangle", "oval",
        "pentagon", "hexagon", "octagon", "triangle", "diamond", "arrow",
        "star", "star5", "star6", "star7", "cloud", "heart", "lightning", "sun", "moon"
      * text: Text to display (optional)
      * left: X position in inches
      * top: Y position in inches
      * width: Width in inches (optional, auto-sized if text provided)
      * height: Height in inches (optional, auto-sized if text provided)
      * color: RGB array like [R, G, B], e.g., [68, 114, 196] for blue
      * text_color: RGB array for text (optional, default white)
      * font_size: Font size in points (optional, default 14)
    - Note: Slide dimensions are ~10" wide × 7.5" tall

12. **save_presentation**
    - Saves the presentation to a file
    - Parameters: presentation_id, output_path

13. **list_presentations**
    - Lists all active presentations
    - Parameters: none

## Color Presets (RGB values):
- Blue: [68, 114, 196]
- Green: [112, 173, 71]
- Orange: [255, 192, 0]
- Red: [192, 0, 0]
- Purple: [112, 48, 160]
- Teal: [0, 176, 240]

## Important Guidelines:
1. Always create a presentation first before adding slides
2. For shapes, position them within slide bounds (0-10 inches width, 0-7.5 inches height)
3. Auto-sizing works when width/height are omitted but text is provided
4. Use appropriate spacing between shapes (at least 0.5 inches)
5. For org charts, timelines, or processes, use add_shape_slide for custom layouts
6. Choose colors that contrast well for readability
"""

    async def start_mcp_session(self):
        """Start a persistent MCP session"""
        self.server_params = StdioServerParameters(
            command="python",
            args=[r"D:\SourceCode\GenAI\MCP\server\ppt\ppt_mcp_server.py"]
        )
        
        # Create stdio client connection
        self.stdio_context = stdio_client(self.server_params)
        self.mcp_read, self.mcp_write = await self.stdio_context.__aenter__()
        
        # Create session
        self.session_context = ClientSession(self.mcp_read, self.mcp_write)
        self.mcp_session = await self.session_context.__aenter__()
        await self.mcp_session.initialize()
        
        print("✓ MCP session started")

    async def close_mcp_session(self):
        """Close the MCP session"""
        if self.mcp_session:
            try:
                await self.session_context.__aexit__(None, None, None)
            except:
                pass
        if self.stdio_context:
            try:
                await self.stdio_context.__aexit__(None, None, None)
            except:
                pass
        self.mcp_session = None
        print("✓ MCP session closed")

    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call an MCP tool and return the result"""
        if not self.mcp_session:
            raise RuntimeError("MCP session not started. Call start_mcp_session() first.")
        
        result = await self.mcp_session.call_tool(tool_name, arguments)
        return result.content[0].text

    async def _call_llm(self, system_prompt: str, messages: List[Dict]) -> str:
        """Call the configured LLM provider and return the response text"""
        
        if self.provider == "anthropic":
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages
            )
            return response.content[0].text
        
        elif self.provider == "openai":
            # Convert messages to OpenAI format (includes system message)
            openai_messages = [{"role": "system", "content": system_prompt}]
            openai_messages.extend(messages)
            
            response = self.openai_client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=openai_messages
            )
            return response.choices[0].message.content
        
        elif self.provider == "bedrock":
            # Format for Bedrock Converse API
            import json
            
            # Build the messages for Bedrock
            bedrock_messages = []
            for msg in messages:
                bedrock_messages.append({
                    "role": msg["role"],
                    "content": [{"text": msg["content"]}]
                })
            
            # Call Bedrock Converse API
            response = self.bedrock_client.converse(
                modelId=self.model,
                messages=bedrock_messages,
                system=[{"text": system_prompt}],
                inferenceConfig={
                    "maxTokens": self.max_tokens,
                    "temperature": 0.7
                }
            )
            
            # Extract text from response
            return response["output"]["message"]["content"][0]["text"]
        
        elif self.provider == "gemini":
            # Gemini doesn't separate system/user messages the same way
            # Combine system prompt with first user message
            full_prompt = f"{system_prompt}\n\n{messages[-1]['content']}"
            
            response = self.gemini_model.generate_content(full_prompt)
            return response.text
        
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the LLM"""
        return f"""You are an expert PowerPoint presentation assistant. You help users create professional presentations by interpreting their natural language requests and making the appropriate MCP tool calls.

{self.tools_documentation}

Your job is to:
1. Understand what the user wants to create
2. Choose the appropriate MCP tools
3. Structure the data correctly for each tool call
4. Make creative decisions about layouts, colors, and positioning
5. Provide the tool calls in JSON format

When responding, output ONLY valid JSON in this format:
{{
  "reasoning": "Brief explanation of your approach",
  "tool_calls": [
    {{
      "tool": "tool_name",
      "arguments": {{...}}
    }},
    ...
  ]
}}

Guidelines:
- Be creative with colors and layouts
- Use appropriate shapes for the content type
- Space elements evenly and professionally
- For complex requests, break them into multiple slides
- Always create the presentation first if it doesn't exist
- Use auto-sizing for shapes when appropriate
- Consider visual hierarchy and flow

Important: Output ONLY the JSON object, no other text or formatting."""

    async def chat(self, user_message: str, presentation_id: str = "my_presentation") -> Dict[str, Any]:
        """
        Process a natural language request and execute the appropriate MCP tools
        
        Args:
            user_message: Natural language request from user
            presentation_id: ID for the presentation (default: "my_presentation")
            
        Returns:
            Dict with results and messages
        """
        print(f"\n{'='*60}")
        print(f"User: {user_message}")
        print(f"{'='*60}\n")
        
        # Add context about current presentation
        context_message = f"{user_message}\n\nContext: Working with presentation_id='{presentation_id}'"
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": context_message
        })
        
        # Call LLM to get tool calls
        print("🤔 Thinking...")
        llm_response = await self._call_llm(self._build_system_prompt(), self.conversation_history)
        
        # Parse the JSON response
        try:
            response_data = json.loads(llm_response)
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing LLM response: {e}")
            print(f"Raw response: {llm_response}")
            return {"error": "Failed to parse LLM response", "raw": llm_response}
        
        reasoning = response_data.get("reasoning", "")
        tool_calls = response_data.get("tool_calls", [])
        
        print(f"💡 Plan: {reasoning}\n")
        
        # Execute each tool call
        results = []
        for i, tool_call in enumerate(tool_calls, 1):
            tool_name = tool_call["tool"]
            arguments = tool_call["arguments"]
            
            print(f"[{i}/{len(tool_calls)}] Calling {tool_name}...")
            print(f"   Arguments: {json.dumps(arguments, indent=2)}")
            
            try:
                result = await self.call_mcp_tool(tool_name, arguments)
                results.append({
                    "tool": tool_name,
                    "status": "success",
                    "result": result
                })
                print(f"   ✓ {result}\n")
            except Exception as e:
                error_msg = str(e)
                results.append({
                    "tool": tool_name,
                    "status": "error",
                    "error": error_msg
                })
                print(f"   ❌ Error: {error_msg}\n")
        
        # Add assistant response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": llm_response
        })
        
        return {
            "reasoning": reasoning,
            "results": results,
            "tool_calls": tool_calls
        }

    async def save_presentation(self, presentation_id: str, output_path: str):
        """Convenience method to save the presentation"""
        result = await self.call_mcp_tool("save_presentation", {
            "presentation_id": presentation_id,
            "output_path": output_path
        })
        print(f"\n✓ {result}")


async def interactive_mode():
    """Run an interactive chat session"""
    print("\n" + "="*60)
    print("PowerPoint LLM Client - Natural Language Interface")
    print("="*60)
    print("\nThis client lets you create PowerPoint presentations using natural language!")
    print("The LLM will automatically choose the right shapes, colors, and layouts.\n")
    print("Commands:")
    print("  - Type your request in natural language")
    print("  - Type 'save' to save the presentation")
    print("  - Type 'exit' to quit")
    print("="*60 + "\n")
    
    # Initialize client
    client = PowerPointLLMClient()
    await client.start_mcp_session()
    
    presentation_id = "my_presentation"
    presentation_created = False
    
    try:
        while True:
            user_input = input("\n💬 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\n👋 Goodbye!")
                break
            
            if user_input.lower() == 'save':
                if not presentation_created:
                    print("⚠️ No presentation created yet!")
                    continue
                
                output_path = input("Output path (default: output/my_presentation.pptx): ").strip()
                if not output_path:
                    output_path = "output/my_presentation.pptx"
                
                await client.save_presentation(presentation_id, output_path)
                continue
            
            # Process the request
            result = await client.chat(user_input, presentation_id)
            
            # Check if presentation was created
            for tool_call in result.get("tool_calls", []):
                if tool_call["tool"] == "create_presentation":
                    presentation_created = True
            
            print(f"\n{'='*60}")
            print(f"✓ Completed {len(result.get('results', []))} action(s)")
            print(f"{'='*60}")
    
    finally:
        await client.close_mcp_session()


async def demo_examples():
    """Run some demo examples"""
    print("\n" + "="*60)
    print("PowerPoint LLM Client - Demo Examples")
    print("="*60 + "\n")
    
    client = PowerPointLLMClient()
    await client.start_mcp_session()
    
    # Example 1: Simple request
    await client.chat(
        "Create a presentation about our Q4 results with a title slide",
        "demo_presentation"
    )
    
    # Example 2: Org chart
    await client.chat(
        "Add an organizational chart showing CEO at top, then 3 directors below, "
        "and 2 teams under each director. Use professional colors.",
        "demo_presentation"
    )
    
    # Example 3: Metrics dashboard
    await client.chat(
        "Create a metrics dashboard slide with 3 circular shapes showing: "
        "95% customer satisfaction, 2.5M users, and $10M revenue. Use green, blue, and gold colors.",
        "demo_presentation"
    )
    
    # Example 4: Process flow
    await client.chat(
        "Add a process flow slide showing: Research → Design → Develop → Test → Launch",
        "demo_presentation"
    )
    
    # Save
    await client.save_presentation("demo_presentation", "output/llm_demo.pptx")
    
    await client.close_mcp_session()
    
    print("\n" + "="*60)
    print("✓ Demo complete! Check output/llm_demo.pptx")
    print("="*60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        asyncio.run(demo_examples())
    else:
        asyncio.run(interactive_mode())
