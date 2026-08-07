#!/usr/bin/env python3
"""
LLM Service - Universal LLM abstraction layer for PMO Agent

Supports multiple LLM providers:
- AWS Bedrock (Claude)
- OpenAI (GPT-4, GPT-3.5)
- Google Gemini
- Azure OpenAI
- Local models (Ollama)

Provides consistent interface regardless of underlying provider.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers"""
    CLAUDE = "claude"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"


@dataclass
class LLMConfig:
    """Configuration for LLM providers"""
    provider: LLMProvider
    model: str
    max_tokens: int = 1000
    temperature: float = 0.1
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    region: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None


@dataclass
class LLMMessage:
    """Universal message format"""
    role: str  # 'user', 'assistant', 'system'
    content: str


@dataclass
class LLMResponse:
    """Universal response format"""
    content: str
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = None
        self._initialize_client()
    
    @abstractmethod
    def _initialize_client(self):
        """Initialize the provider-specific client"""
        pass
    
    @abstractmethod
    async def generate(self, messages: List[LLMMessage]) -> LLMResponse:
        """Generate response from messages"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and configured"""
        pass


class ClaudeProvider(BaseLLMProvider):
    """AWS Bedrock Claude provider"""
    
    def _initialize_client(self):
        try:
            import boto3
            self.client = boto3.client(
                'bedrock-runtime',
                region_name=self.config.region or 'us-east-1'
            )
        except ImportError:
            logger.warning("boto3 not available for Claude provider")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Claude client: {e}")
            self.client = None
    
    async def generate(self, messages: List[LLMMessage]) -> LLMResponse:
        if not self.client:
            raise ValueError("Claude client not available")
        
        # Convert to Claude format
        claude_messages = []
        for msg in messages:
            claude_messages.append({
                'role': msg.role,
                'content': msg.content
            })
        
        body = {
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': self.config.max_tokens,
            'temperature': self.config.temperature,
            'messages': claude_messages
        }
        
        try:
            response = self.client.invoke_model(
                modelId=self.config.model,
                body=json.dumps(body)
            )
            
            result = json.loads(response['body'].read())
            
            return LLMResponse(
                content=result['content'][0]['text'],
                usage=result.get('usage'),
                model=self.config.model,
                provider='claude',
                raw_response=result
            )
            
        except Exception as e:
            logger.error(f"Claude generation failed: {e}")
            raise
    
    def is_available(self) -> bool:
        return self.client is not None


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider"""
    
    def _initialize_client(self):
        try:
            import openai
            if self.config.api_key:
                openai.api_key = self.config.api_key
            if self.config.base_url:
                openai.api_base = self.config.base_url
            self.client = openai
        except ImportError:
            logger.warning("openai package not available")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None
    
    async def generate(self, messages: List[LLMMessage]) -> LLMResponse:
        if not self.client:
            raise ValueError("OpenAI client not available")
        
        # Convert to OpenAI format
        openai_messages = []
        for msg in messages:
            openai_messages.append({
                'role': msg.role,
                'content': msg.content
            })
        
        try:
            response = await self.client.ChatCompletion.acreate(
                model=self.config.model,
                messages=openai_messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                usage=response.usage,
                model=response.model,
                provider='openai',
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise
    
    def is_available(self) -> bool:
        return self.client is not None


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider"""
    
    def _initialize_client(self):
        try:
            import google.generativeai as genai
            if self.config.api_key:
                genai.configure(api_key=self.config.api_key)
            self.client = genai.GenerativeModel(self.config.model)
        except ImportError:
            logger.warning("google-generativeai package not available")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.client = None
    
    async def generate(self, messages: List[LLMMessage]) -> LLMResponse:
        if not self.client:
            raise ValueError("Gemini client not available")
        
        # Combine messages into single prompt for Gemini
        prompt = "\n\n".join([f"{msg.role}: {msg.content}" for msg in messages])
        
        try:
            response = await self.client.generate_content_async(
                prompt,
                generation_config={
                    'max_output_tokens': self.config.max_tokens,
                    'temperature': self.config.temperature
                }
            )
            
            return LLMResponse(
                content=response.text,
                model=self.config.model,
                provider='gemini',
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            raise
    
    def is_available(self) -> bool:
        return self.client is not None


class OllamaProvider(BaseLLMProvider):
    """Local Ollama provider"""
    
    def _initialize_client(self):
        try:
            import aiohttp
            self.client = aiohttp.ClientSession()
            self.base_url = self.config.base_url or "http://localhost:11434"
        except ImportError:
            logger.warning("aiohttp not available for Ollama provider")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Ollama client: {e}")
            self.client = None
    
    async def generate(self, messages: List[LLMMessage]) -> LLMResponse:
        if not self.client:
            raise ValueError("Ollama client not available")
        
        # Convert to Ollama format
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                'role': msg.role,
                'content': msg.content
            })
        
        payload = {
            'model': self.config.model,
            'messages': ollama_messages,
            'stream': False,
            'options': {
                'temperature': self.config.temperature,
                'num_predict': self.config.max_tokens
            }
        }
        
        try:
            async with self.client.post(
                f"{self.base_url}/api/chat",
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return LLMResponse(
                        content=result['message']['content'],
                        model=self.config.model,
                        provider='ollama',
                        raw_response=result
                    )
                else:
                    raise ValueError(f"Ollama API error: {response.status}")
                    
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise
    
    def is_available(self) -> bool:
        return self.client is not None


class LLMService:
    """
    Universal LLM service that provides consistent interface across providers
    
    Supports fallback providers and automatic provider selection
    """
    
    def __init__(self, primary_config: LLMConfig, fallback_configs: Optional[List[LLMConfig]] = None):
        self.primary_config = primary_config
        self.fallback_configs = fallback_configs or []
        self.providers = {}
        self.active_provider = None
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all configured providers"""
        all_configs = [self.primary_config] + self.fallback_configs
        
        for config in all_configs:
            try:
                provider = self._create_provider(config)
                if provider.is_available():
                    self.providers[config.provider] = provider
                    if not self.active_provider:
                        self.active_provider = provider
                        logger.info(f"Primary LLM provider: {config.provider.value}")
            except Exception as e:
                logger.warning(f"Failed to initialize {config.provider.value}: {e}")
    
    def _create_provider(self, config: LLMConfig) -> BaseLLMProvider:
        """Factory method to create provider instances"""
        if config.provider == LLMProvider.CLAUDE:
            return ClaudeProvider(config)
        elif config.provider == LLMProvider.OPENAI:
            return OpenAIProvider(config)
        elif config.provider == LLMProvider.GEMINI:
            return GeminiProvider(config)
        elif config.provider == LLMProvider.OLLAMA:
            return OllamaProvider(config)
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate response using available provider"""
        if not self.active_provider:
            raise ValueError("No LLM providers available")
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role='system', content=system_prompt))
        messages.append(LLMMessage(role='user', content=prompt))
        
        # Try primary provider first, then fallbacks
        for provider_enum, provider in self.providers.items():
            try:
                return await provider.generate(messages)
            except Exception as e:
                logger.warning(f"Provider {provider_enum.value} failed: {e}")
                continue
        
        raise ValueError("All LLM providers failed")
    
    async def analyze_query_intent(self, query: str, business_context: str) -> Dict[str, Any]:
        """Analyze query intent using LLM"""
        
        system_prompt = """You are analyzing a PMO query. Return JSON with:
        - intent: one of [business_lines, all_projects, filtered_projects, all_resources, resource_allocation, general]
        - entities: array of {type, value} objects for mentioned entities
        - requirements: object with analysis requirements
        - format_preference: preferred output format
        - confidence: confidence score 0-1"""
        
        user_prompt = f"""
        Business Context: {business_context}
        
        Query: "{query}"
        
        Analyze this query and return the JSON analysis.
        """
        
        try:
            response = await self.generate(user_prompt, system_prompt)
            # Try to parse as JSON
            try:
                return json.loads(response.content)
            except json.JSONDecodeError:
                # Extract JSON from response if wrapped in text
                import re
                json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    # Fallback to basic analysis
                    return self._fallback_intent_analysis(query)
        except Exception as e:
            logger.warning(f"LLM intent analysis failed: {e}")
            return self._fallback_intent_analysis(query)
    
    def _fallback_intent_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback rule-based intent analysis"""
        query_lower = query.lower()
        
        # Simple pattern matching
        if any(term in query_lower for term in ['business line', 'portfolio', 'product line']):
            intent = 'business_lines'
        elif any(term in query_lower for term in ['resource', 'colleague', 'capacity']) and 'allocation' in query_lower:
            intent = 'resource_allocation'
        elif 'resource' in query_lower or 'colleague' in query_lower:
            intent = 'all_resources'
        elif 'project' in query_lower and 'all' in query_lower:
            intent = 'all_projects'
        elif 'project' in query_lower:
            intent = 'filtered_projects'
        else:
            intent = 'general'
        
        return {
            'intent': intent,
            'entities': [],
            'requirements': {},
            'format_preference': 'structured',
            'confidence': 0.6
        }
    
    async def generate_insights(self, data_summary: str, query: str, context: str) -> str:
        """Generate business insights about data"""
        
        system_prompt = """You are a PMO business analyst. Generate 2-3 concise, actionable business insights based on the data and user query. Focus on trends, risks, opportunities, and recommendations."""
        
        user_prompt = f"""
        Data Summary: {data_summary}
        User Query: {query}
        Context: {context}
        
        Generate business insights:
        """
        
        try:
            response = await self.generate(user_prompt, system_prompt)
            return response.content
        except Exception as e:
            logger.warning(f"Insight generation failed: {e}")
            return f"Data analysis completed. Found relevant information for query: {query}"
    
    def get_active_provider_info(self) -> Dict[str, Any]:
        """Get information about active provider"""
        if not self.active_provider:
            return {'provider': 'none', 'available': False}
        
        return {
            'provider': self.active_provider.config.provider.value,
            'model': self.active_provider.config.model,
            'available': True,
            'fallback_count': len(self.providers) - 1
        }
    
    def switch_provider(self, provider: LLMProvider) -> bool:
        """Switch to different provider if available"""
        if provider in self.providers:
            self.active_provider = self.providers[provider]
            logger.info(f"Switched to LLM provider: {provider.value}")
            return True
        return False


# Convenience functions for common configurations

def create_claude_config(model: str = "anthropic.claude-3-sonnet-20240229-v1:0", region: str = "us-east-1") -> LLMConfig:
    """Create Claude configuration"""
    return LLMConfig(
        provider=LLMProvider.CLAUDE,
        model=model,
        region=region,
        max_tokens=1000,
        temperature=0.1
    )


def create_openai_config(model: str = "gpt-4", api_key: Optional[str] = None) -> LLMConfig:
    """Create OpenAI configuration"""
    return LLMConfig(
        provider=LLMProvider.OPENAI,
        model=model,
        api_key=api_key,
        max_tokens=1000,
        temperature=0.1
    )


def create_gemini_config(model: str = "gemini-pro", api_key: Optional[str] = None) -> LLMConfig:
    """Create Gemini configuration"""
    return LLMConfig(
        provider=LLMProvider.GEMINI,
        model=model,
        api_key=api_key,
        max_tokens=1000,
        temperature=0.1
    )


def create_ollama_config(model: str = "llama2", base_url: str = "http://localhost:11434") -> LLMConfig:
    """Create Ollama configuration"""
    return LLMConfig(
        provider=LLMProvider.OLLAMA,
        model=model,
        base_url=base_url,
        max_tokens=1000,
        temperature=0.1
    )


def create_multi_provider_service(
    primary_provider: LLMProvider = LLMProvider.CLAUDE,
    include_fallbacks: bool = True
) -> LLMService:
    """Create LLM service with multiple provider support"""
    
    # Primary configuration
    if primary_provider == LLMProvider.CLAUDE:
        primary_config = create_claude_config()
    elif primary_provider == LLMProvider.OPENAI:
        primary_config = create_openai_config()
    elif primary_provider == LLMProvider.GEMINI:
        primary_config = create_gemini_config()
    else:
        primary_config = create_claude_config()  # Default fallback
    
    # Fallback configurations
    fallbacks = []
    if include_fallbacks:
        if primary_provider != LLMProvider.OPENAI:
            fallbacks.append(create_openai_config())
        if primary_provider != LLMProvider.GEMINI:
            fallbacks.append(create_gemini_config())
        if primary_provider != LLMProvider.CLAUDE:
            fallbacks.append(create_claude_config())
        fallbacks.append(create_ollama_config())
    
    return LLMService(primary_config, fallbacks)


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_llm_service():
        # Create service with Claude primary, OpenAI fallback
        service = create_multi_provider_service(LLMProvider.CLAUDE)
        
        print(f"Active provider: {service.get_active_provider_info()}")
        
        # Test query analysis
        result = await service.analyze_query_intent(
            "Show me all projects in Market & Sell portfolio",
            "PMO system with business lines and projects"
        )
        print(f"Intent analysis: {result}")
        
        # Test insight generation
        insights = await service.generate_insights(
            "15 projects, 3 portfolios, $2M budget",
            "Show project summary",
            "Portfolio performance review"
        )
        print(f"Insights: {insights}")
    
    asyncio.run(test_llm_service())