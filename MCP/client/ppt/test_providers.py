"""
Test script to verify all LLM providers can be initialized
"""

from ppt_llm_client import PowerPointLLMClient
import os

def test_provider(provider_name: str):
    """Test if a provider can be initialized"""
    print(f"\n{'='*60}")
    print(f"Testing {provider_name.upper()} Provider")
    print('='*60)
    
    try:
        client = PowerPointLLMClient(provider=provider_name)
        print(f"✅ {provider_name.upper()} client initialized successfully!")
        print(f"   Model: {client.model}")
        print(f"   Max tokens: {client.max_tokens}")
        return True
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        return False
    except ImportError as e:
        print(f"⚠️  Package not installed: {e}")
        print(f"   Install with: pip install {provider_name}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("PowerPoint LLM Client - Provider Test")
    print("="*60)
    print("\nTesting all configured providers from .env...\n")
    
    providers = ["bedrock", "anthropic", "openai", "gemini"]
    results = {}
    
    for provider in providers:
        results[provider] = test_provider(provider)
    
    # Summary
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    
    for provider, success in results.items():
        status = "✅ Ready" if success else "❌ Not Available"
        print(f"{provider.upper():<15} {status}")
    
    # Show active provider
    active_provider = os.getenv("LLM_PROVIDER", "bedrock")
    print(f"\n🎯 Active Provider (from .env): {active_provider.upper()}")
    
    if results.get(active_provider):
        print(f"✅ Your configuration is ready to use!")
    else:
        print(f"⚠️  Warning: Active provider '{active_provider}' is not available")
        print("   Either install required packages or change LLM_PROVIDER in .env")
    
    print("\n" + "="*60)
    print("\nTo use the client:")
    print("  python ppt_llm_client.py")
    print("\nTo switch providers, edit .env:")
    print("  LLM_PROVIDER=bedrock  # or anthropic, openai, gemini")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
