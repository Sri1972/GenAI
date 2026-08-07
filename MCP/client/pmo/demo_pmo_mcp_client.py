#!/usr/bin/env python3
"""
Demonstration script showing how to use the unified LLM PMO client
with different providers.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from pmo_mcp_client import UnifiedLLMClient, LLMProvider

def demo_provider_switching():
    """Demonstrate switching between different LLM providers"""
    print("🚀 Multi-LLM PMO Client Demo")
    print("=" * 40)
    
    # Load environment
    load_dotenv()
    
    # Initialize unified client
    client = UnifiedLLMClient()
    print(f"🎯 Initially using: {client.config.provider.value.upper()}")
    
    # Test messages for demonstration
    system_text = "You are a helpful PMO assistant. Respond briefly."
    messages = [{"role": "user", "content": "Hello! Please confirm you're working and tell me what LLM provider is being used."}]
    
    providers_to_test = [
        LLMProvider.ANTHROPIC,
        LLMProvider.OPENAI, 
        LLMProvider.BEDROCK,
        LLMProvider.GEMINI
    ]
    
    print("\n🔄 Testing provider switching (without actual API calls):")
    for provider in providers_to_test:
        try:
            # Switch provider
            original_provider = client.config.provider
            client.config.provider = provider
            client.client = client._create_client()
            
            print(f"   ✅ Successfully switched to {provider.value.upper()}")
            
            # In a real scenario, you would call:
            # response = client.call_llm(system_text, messages)
            # print(f"      Response: {response}")
            
            # Restore original provider for next test
            client.config.provider = original_provider
            client.client = client._create_client()
            
        except Exception as e:
            print(f"   ⚠️  {provider.value.upper()}: {str(e)[:50]}...")
    
    print(f"\n🔄 Restored to original provider: {client.config.provider.value.upper()}")

def demo_configuration_options():
    """Show different configuration options"""
    print("\n⚙️  Configuration Options:")
    print("=" * 40)
    
    client = UnifiedLLMClient()
    config = client.config
    
    print("Current configuration:")
    print(f"   Provider: {config.provider.value}")
    print(f"   Max tokens: {config.max_tokens}")
    
    if config.provider == LLMProvider.ANTHROPIC:
        print(f"   Model: {config.anthropic_model}")
    elif config.provider == LLMProvider.OPENAI:
        print(f"   Model: {config.openai_model}")
        if config.openai_base_url:
            print(f"   Base URL: {config.openai_base_url}")
    elif config.provider == LLMProvider.BEDROCK:
        print(f"   Model: {config.bedrock_model}")
        print(f"   Region: {config.aws_region}")
    elif config.provider == LLMProvider.GEMINI:
        print(f"   Model: {config.gemini_model}")
    
    print("\nTo change providers, set environment variable:")
    print("   LLM_PROVIDER=anthropic  # or openai, bedrock, gemini")

def demo_usage_examples():
    """Show typical usage examples"""
    print("\n📝 Usage Examples:")
    print("=" * 40)
    
    examples = [
        {
            "provider": "anthropic",
            "description": "Using Anthropic Claude for detailed analysis",
            "query": "Analyze the Q4 project portfolio and provide insights"
        },
        {
            "provider": "openai", 
            "description": "Using OpenAI GPT for general queries",
            "query": "List all active projects and their status"
        },
        {
            "provider": "bedrock",
            "description": "Using AWS Bedrock for enterprise deployment",
            "query": "Show resource allocation across all teams"
        },
        {
            "provider": "gemini",
            "description": "Using Google Gemini for fast responses",
            "query": "Create a chart of monthly budget vs actual spend"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['description']}:")
        print(f"   Provider: {example['provider']}")
        print(f"   Query: \"{example['query']}\"")
    print(f"   Command: python pmo_mcp_client.py --provider {example['provider']}")

def demo_api_key_setup():
    """Show how to set up API keys for each provider"""
    print("\n🔑 API Key Setup Guide:")
    print("=" * 40)
    
    setup_guides = [
        {
            "provider": "Anthropic Claude",
            "steps": [
                "1. Go to https://console.anthropic.com/",
                "2. Create account and get API key",
                "3. Set ANTHROPIC_API_KEY=sk-ant-api03-... in .env",
                "4. Set LLM_PROVIDER=anthropic"
            ]
        },
        {
            "provider": "OpenAI GPT",
            "steps": [
                "1. Go to https://platform.openai.com/api-keys",
                "2. Create API key",
                "3. Set OPENAI_API_KEY=sk-proj-... in .env",
                "4. Set LLM_PROVIDER=openai"
            ]
        },
        {
            "provider": "AWS Bedrock",
            "steps": [
                "1. Configure AWS credentials: aws configure",
                "2. Enable Bedrock models in AWS console", 
                "3. Set BEDROCK_MODEL=anthropic.claude-3-sonnet-... in .env",
                "4. Set LLM_PROVIDER=bedrock"
            ]
        },
        {
            "provider": "Google Gemini",
            "steps": [
                "1. Go to https://aistudio.google.com/app/apikey",
                "2. Create API key",
                "3. Set GEMINI_API_KEY=AIza... in .env",
                "4. Set LLM_PROVIDER=gemini"
            ]
        }
    ]
    
    for guide in setup_guides:
        print(f"\n{guide['provider']}:")
        for step in guide['steps']:
            print(f"   {step}")

def main():
    """Run the demonstration"""
    print("🎭 Unified LLM PMO Client Demonstration")
    print("=" * 50)
    
    demo_provider_switching()
    demo_configuration_options()
    demo_usage_examples()
    demo_api_key_setup()
    
    print("\n🎯 Next Steps:")
    print("=" * 50)
    print("1. Configure your preferred provider in .env file")
    print("2. Install required packages: pip install anthropic openai boto3 google-generativeai")
    print("3. Run the client: python pmo_mcp_client.py")
    print("4. Or run with specific provider: python pmo_mcp_client.py --provider anthropic")
    print("5. Switch providers in REPL: :provider openai")
    
    print("\n📚 Documentation:")
    print("   Full guide: README_unified_llm.md")
    print("   Configuration: .env.example")
    print("   Testing: python test_unified_llm.py")

if __name__ == "__main__":
    main()