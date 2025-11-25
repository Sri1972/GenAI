"""
LLM Utilities for NLP to Structured Data System - Simplified Version

Provides interface for Large Language Model operations including
query understanding, intent analysis, and response generation.
Includes Claude Bedrock integration.
"""

import asyncio
import logging
import os
import json
import re
from typing import Any, Dict, List, Optional, Union
from abc import ABC, abstractmethod
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

# Import LLM providers
try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response from LLM."""
        pass


class ClaudeBedrockProvider(BaseLLMProvider):
    """Simple Claude Bedrock provider."""
    
    def __init__(self):
        self.model = os.getenv('BEDROCK_MODEL', 'anthropic.claude-sonnet-4')
        self.logger = logging.getLogger("llm_utils.claude_bedrock")
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Claude on AWS Bedrock."""
        try:
            if not HAS_BOTO3:
                return "Mock response: Claude Bedrock would process this request."
            
            # Try to use Bedrock
            region = os.getenv('AWS_REGION', 'us-east-1')
            client = boto3.client('bedrock-runtime', region_name=region)
            
            # Prepare proper payload for Claude/Anthropic models
            max_tokens = kwargs.get('max_tokens', 1000)
            
            # Format for Anthropic models on Bedrock
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ]
            }
            
            response = client.invoke_model(
                body=json.dumps(payload).encode('utf-8'),
                contentType='application/json',
                accept='application/json',
                modelId=self.model
            )
            
            result = json.loads(response['body'].read().decode('utf-8'))
            
            # Parse Claude response format
            if 'content' in result and isinstance(result['content'], list):
                if result['content'] and 'text' in result['content'][0]:
                    return result['content'][0]['text']
            
            # Fallback to string representation
            return str(result)
            
        except Exception as e:
            self.logger.warning(f"Bedrock call failed: {e}")
            return f"Claude would analyze: {prompt[:100]}... [Error: {str(e)[:50]}]"


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing."""
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate mock response."""
        if "intent" in prompt.lower():
            return json.dumps({
                "primary_action": "describe",
                "target_columns": [],
                "filters": {},
                "grouping": [],
                "aggregations": {},
                "sorting": {},
                "output_format": "table",
                "confidence": 0.8
            })
        elif "summary" in prompt.lower():
            return "This is a mock summary of the dataset showing key patterns and insights."
        else:
            return "I understand your request and will help you analyze the data."


class LLMProcessor:
    """Main LLM processor for handling natural language operations."""
    
    def __init__(self, provider: Optional[BaseLLMProvider] = None, default_provider: str = "claude_bedrock"):
        self.logger = logging.getLogger("utils.llm_processor")
        
        if provider:
            self.provider = provider
        else:
            self.provider = self._create_default_provider(default_provider)
    
    def _create_default_provider(self, provider_name: str) -> BaseLLMProvider:
        """Create default LLM provider."""
        if provider_name == "claude_bedrock":
            try:
                return ClaudeBedrockProvider()
            except Exception as e:
                self.logger.warning(f"Failed to create Claude Bedrock provider: {e}")
        
        # Fallback to mock provider
        self.logger.warning("Using mock LLM provider.")
        return MockLLMProvider()

    async def process(self, prompt: str, **kwargs) -> str:
        """Process prompt and generate response."""
        try:
            response = await self.provider.generate_response(prompt, **kwargs)
            return response
        except Exception as e:
            self.logger.error(f"Error processing prompt: {e}")
            raise

    async def analyze_query_intent(self, query: str, data_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user query to understand intent."""
        prompt = f"""
        Analyze this user query for a structured dataset and extract the intent.
        
        User Query: "{query}"
        
        Available Data Schema:
        {json.dumps(data_schema, indent=2)}
        
        Return a JSON object with the following structure:
        {{
            "primary_action": "describe",
            "target_columns": [],
            "filters": {{}},
            "grouping": [],
            "aggregations": {{}},
            "sorting": {{}},
            "output_format": "table",
            "confidence": 0.95
        }}
        """
        
        try:
            response = await self.provider.generate_response(prompt)
            # Try to parse JSON response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            self.logger.error(f"Error analyzing query intent: {e}")
        
        # Return default intent
        return {
            "primary_action": "describe",
            "target_columns": [],
            "filters": {},
            "grouping": [],
            "aggregations": {},
            "sorting": {},
            "output_format": "table",
            "confidence": 0.1
        }

    async def generate_data_summary(self, data_info: Dict[str, Any]) -> str:
        """Generate a summary of the data."""
        prompt = f"""
        Provide a concise summary of this dataset:
        
        {json.dumps(data_info, indent=2)}
        
        Include key insights about data size, structure, and patterns.
        """
        
        try:
            return await self.provider.generate_response(prompt)
        except Exception as e:
            self.logger.error(f"Error generating data summary: {e}")
            return "Unable to generate summary due to an error."

    async def explain_results(self, query: str, results: Any, context: Dict[str, Any]) -> str:
        """Explain query results in natural language."""
        prompt = f"""
        Explain these query results clearly:
        
        Original Query: "{query}"
        Results: {str(results)[:500]}...
        Context: {json.dumps(context, indent=2)}
        """
        
        try:
            return await self.provider.generate_response(prompt)
        except Exception as e:
            self.logger.error(f"Error explaining results: {e}")
            return "Results processed successfully."

    async def suggest_follow_up_queries(self, original_query: str, results: Any, data_schema: Dict[str, Any]) -> List[str]:
        """Suggest follow-up queries based on current results."""
        prompt = f"""
        Based on this query and results, suggest 3-5 follow-up questions:
        
        Original Query: "{original_query}"
        Schema: {json.dumps(data_schema, indent=2)}
        
        Return as a simple list of questions.
        """
        
        try:
            response = await self.provider.generate_response(prompt)
            # Parse suggestions into list
            suggestions = [line.strip() for line in response.split('\n') 
                         if line.strip() and ('?' in line or line.lower().startswith(('what', 'how', 'why')))]
            return suggestions[:5]
        except Exception as e:
            self.logger.error(f"Error generating suggestions: {e}")
            return []


# Convenience function for easy access
def get_llm_processor(provider_name: str = "claude_bedrock") -> LLMProcessor:
    """Get an LLM processor instance with the specified provider."""
    return LLMProcessor(default_provider=provider_name)


# Direct Claude Bedrock function for simple usage
async def call_claude_bedrock(prompt: str, system_text: Optional[str] = None, max_tokens: int = 1000, **kwargs) -> str:
    """Direct function to call Claude via Bedrock."""
    provider = ClaudeBedrockProvider()
    return await provider.generate_response(prompt, max_tokens=max_tokens, **kwargs)