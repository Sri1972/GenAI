from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import traceback
import os
from dotenv import load_dotenv

# Set UTF-8 encoding for Windows compatibility with Unicode characters
if os.name == 'nt':  # Windows
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    import locale
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except:
            pass

import json
import re
import requests
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from abc import ABC, abstractmethod

# Optional LLM provider imports
try:
    import boto3
    import botocore
    from botocore.awsrequest import AWSRequest
    from botocore.auth import SigV4Auth
except Exception:
    boto3 = None
    botocore = None

try:
    import anthropic
except Exception:
    anthropic = None

try:
    import openai
except Exception:
    openai = None

try:
    import google.generativeai as genai
except Exception:
    genai = None

# Additional imports
import sys
import hashlib
import subprocess
import urllib.request
import shutil
from pathlib import Path
from datetime import datetime
import uuid
import argparse
import webbrowser

# Load environment variables
load_dotenv('.env')

# Unified LLM Provider Framework
class LLMProvider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    BEDROCK = "bedrock"
    GEMINI = "gemini"

class LLMConfig:
    def __init__(self):
        self.provider = LLMProvider.BEDROCK  # Default provider
        
        # Anthropic settings
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.anthropic_model = os.getenv('ANTHROPIC_MODEL', 'claude-3-sonnet-20240229')
        
        # OpenAI settings
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-4')
        self.openai_base_url = os.getenv('OPENAI_BASE_URL')
        
        # Bedrock settings
        self.bedrock_model = os.getenv('BEDROCK_MODEL', 'anthropic.claude-sonnet-4')
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self.bedrock_anthropic_version = os.getenv('BEDROCK_ANTHROPIC_VERSION', '20250514')
        
        # Gemini settings
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.gemini_model = os.getenv('GEMINI_MODEL', 'gemini-pro')

class BaseLLMClient(ABC):
    @abstractmethod
    def call(self, system_text: Optional[str], messages: List[Dict], max_tokens: int = 1000) -> str:
        pass

class AnthropicClient(BaseLLMClient):
    def __init__(self, config: LLMConfig):
        self.config = config
        if not anthropic:
            raise ImportError("anthropic package not available")
        if not config.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    
    def call(self, system_text: Optional[str], messages: List[Dict], max_tokens: int = 1000) -> str:
        try:
            # Convert messages format
            anthropic_messages = []
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role in ['user', 'assistant']:
                    anthropic_messages.append({"role": role, "content": content})
            
            kwargs = {
                "model": self.config.anthropic_model,
                "max_tokens": max_tokens,
                "messages": anthropic_messages
            }
            
            if system_text:
                kwargs["system"] = system_text
            
            response = self.client.messages.create(**kwargs)
            return response.content[0].text if response.content else ""
        except Exception as e:
            raise Exception(f"Anthropic API error: {e}")

class OpenAIClient(BaseLLMClient):
    def __init__(self, config: LLMConfig):
        self.config = config
        if not openai:
            raise ImportError("openai package not available")
        if not config.openai_api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        
        kwargs = {"api_key": config.openai_api_key}
        if config.openai_base_url:
            kwargs["base_url"] = config.openai_base_url
        self.client = openai.OpenAI(**kwargs)
    
    def call(self, system_text: Optional[str], messages: List[Dict], max_tokens: int = 1000) -> str:
        try:
            # Convert messages format
            openai_messages = []
            if system_text:
                openai_messages.append({"role": "system", "content": system_text})
            
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                openai_messages.append({"role": role, "content": content})
            
            response = self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=openai_messages,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content if response.choices else ""
        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")

class BedrockClient(BaseLLMClient):
    def __init__(self, config: LLMConfig):
        self.config = config
        if not boto3:
            raise ImportError("boto3 package not available")
    
    def call(self, system_text: Optional[str], messages: List[Dict], max_tokens: int = 1000) -> str:
        return call_bedrock(system_text, messages, max_tokens, self.config.bedrock_model)

class GeminiClient(BaseLLMClient):
    def __init__(self, config: LLMConfig):
        self.config = config
        if not genai:
            raise ImportError("google-generativeai package not available")
        if not config.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        genai.configure(api_key=config.gemini_api_key)
        self.model = genai.GenerativeModel(config.gemini_model)
    
    def call(self, system_text: Optional[str], messages: List[Dict], max_tokens: int = 1000) -> str:
        try:
            # Convert messages to Gemini format
            prompt_parts = []
            if system_text:
                prompt_parts.append(f"System: {system_text}")
            
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                prompt_parts.append(f"{role.capitalize()}: {content}")
            
            prompt = "\n\n".join(prompt_parts)
            response = self.model.generate_content(prompt)
            return response.text if response.text else ""
        except Exception as e:
            raise Exception(f"Gemini API error: {e}")

class UnifiedLLMClient:
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.client = self._create_client()
    
    def _create_client(self) -> BaseLLMClient:
        if self.config.provider == LLMProvider.ANTHROPIC:
            return AnthropicClient(self.config)
        elif self.config.provider == LLMProvider.OPENAI:
            return OpenAIClient(self.config)
        elif self.config.provider == LLMProvider.BEDROCK:
            return BedrockClient(self.config)
        elif self.config.provider == LLMProvider.GEMINI:
            return GeminiClient(self.config)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.config.provider}")
    
    def call_llm(self, system_text: Optional[str], messages: List[Dict], 
                max_tokens: int = 1000, model: Optional[str] = None) -> str:
        # Temporarily override model if specified
        original_model = None
        if model:
            if self.config.provider == LLMProvider.ANTHROPIC:
                original_model = self.config.anthropic_model
                self.config.anthropic_model = model
            elif self.config.provider == LLMProvider.OPENAI:
                original_model = self.config.openai_model
                self.config.openai_model = model
            elif self.config.provider == LLMProvider.BEDROCK:
                original_model = self.config.bedrock_model
                self.config.bedrock_model = model
            elif self.config.provider == LLMProvider.GEMINI:
                original_model = self.config.gemini_model
                self.config.gemini_model = model
        
        try:
            result = self.client.call(system_text, messages, max_tokens)
            return result
        finally:
            # Restore original model if overridden
            if model and original_model:
                if self.config.provider == LLMProvider.ANTHROPIC:
                    self.config.anthropic_model = original_model
                elif self.config.provider == LLMProvider.OPENAI:
                    self.config.openai_model = original_model
                elif self.config.provider == LLMProvider.BEDROCK:
                    self.config.bedrock_model = original_model
                elif self.config.provider == LLMProvider.GEMINI:
                    self.config.gemini_model = original_model

# Global LLM client instance
llm_client = UnifiedLLMClient()

# Legacy function for backward compatibility
def call_bedrock(system_text: Optional[str], messages: List[Dict], 
                max_tokens: int = 1000, model: Optional[str] = None) -> str:
    """Legacy function that now routes to unified LLM client when not using Bedrock directly"""
# Bedrock configuration: user should add BEDROCK_API_KEY and optional BEDROCK_ENDPOINT to .env
# If you have AWS credentials configured and boto3 available, boto3 Bedrock Runtime client will be used.
BEDROCK_API_KEY = os.getenv('BEDROCK_API_KEY')
BEDROCK_MODEL = os.getenv('BEDROCK_MODEL', 'anthropic.claude-sonnet-4')
# Read raw endpoint and sanitize common mistakes (f-string literal, placeholder, surrounding quotes)
_raw_ep = os.getenv('BEDROCK_ENDPOINT')
if _raw_ep:
    ep = _raw_ep.strip()
    # strip leading/trailing quotes if present
    if (ep.startswith('"') and ep.endswith('"')) or (ep.startswith("'") and ep.endswith("'")):
        ep = ep[1:-1]
    # handle Python f-string literal like f"https://.../{BEDROCK_MODEL}/invoke"
    if ep.startswith('f"') or ep.startswith("f'"):
        # remove the f"..." wrapper
        ep = ep[2:-1] if len(ep) > 2 else ''
    # replace placeholder {BEDROCK_MODEL} if present
    if '{BEDROCK_MODEL}' in ep and BEDROCK_MODEL:
        ep = ep.replace('{BEDROCK_MODEL}', BEDROCK_MODEL)
    BEDROCK_ENDPOINT = ep
else:
    BEDROCK_ENDPOINT = None

# Anthropic/Claude models on Bedrock often require an 'anthropic_version' field; allow override via env
_env_anth = os.getenv('BEDROCK_ANTHROPIC_VERSION') or os.getenv('ANTHROPIC_VERSION')
if _env_anth:
    BEDROCK_ANTHROPIC_VERSION = _env_anth
else:
    # Try to infer a sensible anthropic_version from BEDROCK_MODEL, e.g.
    # 'global.anthropic.claude-sonnet-4-20250514-v1:0' -> 'claude-sonnet-4-20250514-v1'
    try:
        if BEDROCK_MODEL and ('anthropic' in BEDROCK_MODEL or 'claude' in BEDROCK_MODEL):
            # take last dot-separated segment and strip any trailing :<num>
            seg = BEDROCK_MODEL.split('.')[-1]
            seg = seg.split(':')[0]
            BEDROCK_ANTHROPIC_VERSION = seg
        else:
            BEDROCK_ANTHROPIC_VERSION = '20250514'
    except Exception:
        BEDROCK_ANTHROPIC_VERSION = '20250514'


def _messages_to_prompt(system_text: str | None, messages: list) -> str:
    """Flatten role-based messages into a single prompt string suitable for Bedrock-style invocation.
    This preserves roles by prefixing each turn with 'System:', 'User:' or 'Assistant:'.
    """
    parts = []
    if system_text:
        parts.append(f"System: {system_text}")
    for m in messages:
        role = m.get('role', 'user')
        content = m.get('content', '')
        label = role.capitalize() if role else 'User'
        parts.append(f"{label}: {content}")
    return "\n\n".join(parts)


def call_bedrock(system_text: str | None, messages: list, max_tokens: int = 1000, model: str | None = None) -> str:
    """Legacy Bedrock function - now handles actual Bedrock calls for the unified client.
    
    When called by the unified client, this provides the original Bedrock functionality.
    When called directly, it can route to the unified client if desired.
    """
    # If we're being called by the unified client, use the original Bedrock logic
    # Otherwise, we could route to the unified client
    
    model_id = model or BEDROCK_MODEL
    
    # Build conv messages in the shape Bedrock expects (role + list of {'text':...})
    conv_msgs = []
    if system_text:
        conv_msgs.append({'role': 'system', 'content': [{'text': str(system_text)}]})
    for m in messages:
        role = m.get('role', 'user')
        content = m.get('content', '')
        if isinstance(content, list):
            conv_content = []
            for c in content:
                if isinstance(c, dict) and 'text' in c:
                    conv_content.append(c)
                else:
                    conv_content.append({'text': str(c)})
        else:
            conv_content = [{'text': str(content)}]
        conv_msgs.append({'role': role, 'content': conv_content})

    def _parse_converse_resp(resp):
        try:
            out = resp.get('output') or {}
            if isinstance(out, dict):
                m = out.get('message') or {}
                content = m.get('content') or []
                if isinstance(content, list) and content:
                    first = content[0]
                    if isinstance(first, dict) and 'text' in first:
                        return first['text']
            return json.dumps(resp)
        except Exception:
            return str(resp)

    # If boto3 is available, try the converse() path for Anthropic-like models first
    if boto3 is not None and model_id and ('anthropic' in model_id.lower() or 'claude' in model_id.lower() or 'sonnet' in model_id.lower()):
        try:
            region = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'us-east-1'
            client = boto3.client('bedrock-runtime', region_name=region)
        except Exception:
            client = None

        if client is not None and hasattr(client, 'converse'):
            # Map system -> user with prefix because Converse only accepts user/assistant
            safe_msgs = []
            for m in conv_msgs:
                role = m.get('role')
                if role == 'system':
                    # merge content list into a single text
                    cont = m.get('content') or []
                    text = ''
                    if isinstance(cont, list) and cont:
                        first = cont[0]
                        text = first.get('text') if isinstance(first, dict) else str(first)
                    else:
                        text = str(cont)
                    safe_msgs.append({'role': 'user', 'content': [{'text': '[SYSTEM] ' + text}]})
                else:
                    safe_msgs.append(m)

            conv_kw = {'modelId': model_id, 'messages': safe_msgs}
            if BEDROCK_ANTHROPIC_VERSION:
                conv_kw['additionalModelRequestFields'] = {'anthropic_version': BEDROCK_ANTHROPIC_VERSION}

            try:
                # print('call_bedrock: attempting client.converse() with model:', model_id)  # Debug: commented for cleaner output
                resp = client.converse(**conv_kw)
                return _parse_converse_resp(resp)
            except Exception as e:
                # If the service complains that anthropic_version conflicts with the profile,
                # retry once without that field.
                emsg = ''
                try:
                    emsg = str(e)
                except Exception:
                    pass
                if 'anthropic_version' in emsg and ('conflict' in emsg or 'conflicts with' in emsg):
                    try:
                        # print('Retrying Bedrock call without version conflict')  # Debug: commented for cleaner output
                        conv_kw.pop('additionalModelRequestFields', None)
                        resp2 = client.converse(**conv_kw)
                        return _parse_converse_resp(resp2)
                    except Exception:
                        # print('call_bedrock: converse() retry without anthropic_version failed')  # Debug: commented
                        traceback.print_exc()
                else:
                    # print('call_bedrock: converse() failed; will fall back to HTTP or invoke_model')  # Debug: commented
                    traceback.print_exc()

    # Fallback path: either boto3 invoke_model or HTTP POST to BEDROCK_ENDPOINT
    prompt = _messages_to_prompt(system_text, messages)

    # Try boto3 invoke_model if available
    if boto3 is not None and model_id:
        try:
            region = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'us-east-1'
            client2 = boto3.client('bedrock-runtime', region_name=region)
            payload = {'input': prompt, 'max_tokens': max_tokens}
            # include anthropic_version for Anthropic-like modelIds
            if model_id and ('anthropic' in model_id.lower() or 'claude' in model_id.lower() or 'sonnet' in model_id.lower()):
                if BEDROCK_ANTHROPIC_VERSION:
                    payload['anthropic_version'] = BEDROCK_ANTHROPIC_VERSION
            body = json.dumps(payload).encode('utf-8')
            resp = client2.invoke_model(body=body, contentType='application/json', accept='application/json', modelId=model_id)
            # read streaming body
            try:
                raw = resp['body'].read()
            except Exception:
                raw = resp.get('body') or b''
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8', errors='ignore')
            try:
                j = json.loads(raw)
                # common shapes
                if isinstance(j, dict):
                    if 'messages' in j and isinstance(j['messages'], list) and j['messages']:
                        first = j['messages'][0]
                        if isinstance(first, dict) and 'content' in first:
                            return first['content']
                    if 'results' in j and isinstance(j['results'], list) and j['results']:
                        first = j['results'][0]
                        if isinstance(first, dict) and 'content' in first:
                            return first['content']
                    if 'output' in j:
                        return j['output']
                return raw
            except Exception:
                return raw
        except Exception:
            traceback.print_exc()

    # Final fallback: HTTP POST to BEDROCK_ENDPOINT using x-api-key or SigV4 if botocore available
    if BEDROCK_ENDPOINT:
        try:
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
            body_obj = {'modelId': model_id, 'input': prompt, 'max_tokens': max_tokens}
            if model_id and ('anthropic' in model_id.lower() or 'claude' in model_id.lower() or 'sonnet' in model_id.lower()):
                if BEDROCK_ANTHROPIC_VERSION:
                    body_obj['anthropic_version'] = BEDROCK_ANTHROPIC_VERSION
            body = json.dumps(body_obj)
            if BEDROCK_API_KEY and botocore is None:
                headers['x-api-key'] = BEDROCK_API_KEY
                r = requests.post(BEDROCK_ENDPOINT, headers=headers, data=body.encode('utf-8'), timeout=30)
                try:
                    return r.text
                except Exception:
                    return str(r)
            elif botocore is not None:
                # Sign with SigV4
                try:
                    region = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'us-east-1'
                    aws_req = AWSRequest(method='POST', url=BEDROCK_ENDPOINT, data=body, headers=headers)
                    session = botocore.session.get_session()
                    creds = session.get_credentials()
                    if creds is None:
                        raise RuntimeError('No AWS credentials available for SigV4 signing')
                    frozen_creds = creds.get_frozen_credentials()
                    sig = SigV4Auth(frozen_creds, 'bedrock-runtime', region)
                    sig.add_auth(aws_req)
                    signed_headers = dict(aws_req.headers)
                    r = requests.post(BEDROCK_ENDPOINT, headers=signed_headers, data=body.encode('utf-8'), timeout=30)
                    try:
                        return r.text
                    except Exception:
                        return str(r)
                except Exception:
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()

    return ''
    # End of call_bedrock

# Short-lived in-process chat memory
chat_memories = {}
MEMORY_MAX_MESSAGES = 200
# Directory to store per-chat memory JSON files
CHAT_MEMORY_DIR = Path(__file__).resolve().parent / 'chat_memory'


def ensure_memory_dir():
    try:
        CHAT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def memory_file_for(chat_id: str) -> Path:
    # sanitize chat_id for filename
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', chat_id)[:64]
    ensure_memory_dir()
    return CHAT_MEMORY_DIR / f"{safe}.json"


def load_chat_memory(chat_id: str):
    """Load persisted chat memory for chat_id into the in-process chat_memories dict.
    Returns the loaded list (may be empty)"""
    path = memory_file_for(chat_id)
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    chat_memories[chat_id] = data[-MEMORY_MAX_MESSAGES:]
                    return chat_memories[chat_id]
        except Exception as e:
            # print(f"Failed to load chat memory for {chat_id}: {e}")  # Debug: commented
            pass  # Silently handle file loading errors
    # ensure key exists
    chat_memories.setdefault(chat_id, [])
    return chat_memories[chat_id]


def save_chat_memory(chat_id: str, messages):
    """Atomically save the provided messages list for chat_id to disk."""
    path = memory_file_for(chat_id)
    try:
        tmp = path.with_suffix('.json.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(messages[-MEMORY_MAX_MESSAGES:], f, ensure_ascii=False, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        try:
            tmp.replace(path)
        except Exception:
            # fallback to move
            os.replace(str(tmp), str(path))
    except Exception as e:
        # print(f"Failed to save chat memory for {chat_id}: {e}")  # Debug: commented
        pass  # Silently handle file saving errors


def set_chat_memory(chat_id: str, messages):
    """Assign into in-memory store and persist to disk."""
    chat_memories[chat_id] = messages[-MEMORY_MAX_MESSAGES:]
    try:
        save_chat_memory(chat_id, chat_memories[chat_id])
    except Exception:
        pass

#server_path = Path(__file__).resolve().parents[2] / 'server' / 'pmo' / 'pmo.py'
server_path = Path(__file__).resolve().parents[2] / 'server' / 'pmo' / 'server.py'


server_params = StdioServerParameters(
    command=sys.executable,
    args=[str(server_path)]
)

# Chart server parameters for D3.js/Chart.js generation
chart_server_path = Path(__file__).resolve().parents[2] / 'server' / 'charts' / 'mcp-d3-stdio-custom' / 'd3_chart_mcp.py'

chart_server_params = StdioServerParameters(
    command=sys.executable,
    args=[str(chart_server_path)]
)


def transform_resource_data_to_chartjs(data):
    """Transform resource allocation data to Chart.js format.
    Handles both old format (direct list) and new format (dict with resource_details and data).
    """
    # Handle new API format with resource_details and data structure
    if isinstance(data, dict):
        if 'data' in data and isinstance(data['data'], list):
            # New format - extract the data array
            allocation_data = data['data']
            resource_details = data.get('resource_details', {})
            resource_name = resource_details.get('resource_name', 'Resource') if resource_details else 'Resource'
        elif 'result' in data and isinstance(data['result'], dict):
            # Handle tool output wrapper with new format
            result = data['result']
            if 'data' in result and isinstance(result['data'], list):
                allocation_data = result['data']
                resource_details = result.get('resource_details', {})
                resource_name = resource_details.get('resource_name', 'Resource') if resource_details else 'Resource'
            else:
                # Fallback for unexpected structure
                allocation_data = []
                resource_name = 'Resource'
        else:
            # Fallback for unexpected structure
            allocation_data = []
            resource_name = 'Resource'
    elif isinstance(data, list):
        # Old format - direct list of allocation data
        allocation_data = data
        resource_name = 'Resource'
    else:
        return data
    
    if not allocation_data:
        return data
    
    try:
        labels = []
        capacity_data = []
        planned_data = []
        actual_data = []
        available_data = []
        
        for period in allocation_data:
            # Create readable period labels
            start = period.get('start_date', '')
            end = period.get('end_date', '')
            if start and end:
                try:
                    from datetime import datetime
                    start_date = datetime.strptime(start, '%Y-%m-%d')
                    end_date = datetime.strptime(end, '%Y-%m-%d')
                    
                    if start_date.month == end_date.month:
                        label = start_date.strftime('%b %Y')
                    else:
                        label = f"{start_date.strftime('%b')}-{end_date.strftime('%b %Y')}"
                except:
                    label = f"{start[:7]} to {end[:7]}"
            else:
                label = f"Period {len(labels) + 1}"
            
            labels.append(label)
            capacity_data.append(period.get('total_capacity', 0))
            planned_data.append(period.get('allocation_hours_planned', 0))
            actual_data.append(period.get('allocation_hours_actual', 0))
            available_data.append(period.get('available_capacity', 0))
        
        # Return Chart.js format with resource name in title
        return {
            "labels": labels,
            "datasets": [
                {
                    "label": "Total Capacity",
                    "data": capacity_data,
                    "borderColor": "rgb(54, 162, 235)",
                    "backgroundColor": "rgba(54, 162, 235, 0.2)",
                    "borderWidth": 2,
                    "tension": 0.1
                },
                {
                    "label": "Planned Hours",
                    "data": planned_data,
                    "borderColor": "rgb(255, 99, 132)",
                    "backgroundColor": "rgba(255, 99, 132, 0.2)",
                    "borderWidth": 2,
                    "tension": 0.1
                },
                {
                    "label": "Available Capacity",
                    "data": available_data,
                    "borderColor": "rgb(75, 192, 192)",
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "borderWidth": 2,
                    "tension": 0.1
                },
                {
                    "label": "Actual Hours",
                    "data": actual_data,
                    "borderColor": "rgb(255, 206, 86)",
                    "backgroundColor": "rgba(255, 206, 86, 0.2)",
                    "borderWidth": 2,
                    "borderDash": [5, 5],
                    "tension": 0.1
                }
            ],
            "title": f"Resource Capacity and Allocation for {resource_name}"
        }
    except Exception as e:
        print(f"Data transformation error: {e}")
        return data


def forward_chart_json_to_d3_mcp(chart_payload: dict, timeout: int = 30) -> str | None:
    """Use the MCP D3 server to generate a chart. Returns saved HTML path or None."""
    try:
        import asyncio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        
        async def generate_chart():
            d3_mcp_server = Path(__file__).resolve().parents[1] / 'server' / 'charts' / 'mcp-d3-stdio-custom' / 'd3_chart_mcp.py'
            print(f"ðŸ” Looking for D3 MCP server at: {d3_mcp_server}")
            if not d3_mcp_server.exists():
                print('âš ï¸  MCP D3 server not found, falling back to STDIO')
                return None
                
            server_params = StdioServerParameters(
                command=sys.executable,
                args=[str(d3_mcp_server)]
            )
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Call the render_chart tool with proper data structure
                    tool_args = chart_payload.get("arguments", {})
                    chart_data = tool_args.get("data", {})
                    chart_type = tool_args.get("chart_type", "line")
                    chart_title = tool_args.get("title", "Chart")
                    
                    result = await session.call_tool(
                        "render_from_dataset",
                        arguments={
                            "chart_type": chart_type,
                            "data": chart_data,
                            "title": chart_title
                        }
                    )
                    
                    if result and hasattr(result, 'content') and result.content:
                        # Extract HTML path from the result
                        content_str = str(result.content[0].text) if result.content else ""
                        # Look for HTML file path in the response
                        import re
                        path_match = re.search(r'HTML file saved to: (.+\.html)', content_str)
                        if path_match:
                            return path_match.group(1)
                    
                    return None
        
        # Run the async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(generate_chart())
        
    except ImportError:
        print('[WARNING] MCP library unavailable for chart generation')
        return None
    except Exception as e:
        print(f'[WARNING] MCP server error: {str(e)[:100]}')
        return None


async def run(query: str, chat_id: str = "default"):
    try:
        print("=" * 60)
        print("Starting PMO MCP Client")
        print("=" * 60)
        print(f"[1/5] Connecting to PMO MCP server...")
        print(f"       Server path: {server_path}")
        async with stdio_client(server_params) as (pmo_reader, pmo_writer):
            async with ClientSession(pmo_reader, pmo_writer) as pmo_session:
                await pmo_session.initialize()
                print(f"[2/5] ✓ PMO MCP server initialized successfully")
                
                # Connect to Chart MCP server
                print(f"[3/5] Attempting to connect to Chart MCP server...")
                print(f"       Server path: {chart_server_path}")
                chart_session = None
                try:
                    async with stdio_client(chart_server_params) as (chart_reader, chart_writer):
                        async with ClientSession(chart_reader, chart_writer) as chart_session:
                            await chart_session.initialize()
                            print(f"[4/5] ✓ Chart MCP server initialized successfully")
                            print(f"[5/5] Both servers ready - proceeding to tool discovery...")
                            print("=" * 60)
                            
                            # Continue with main logic using both sessions
                            return await run_with_sessions(query, chat_id, pmo_session, chart_session)
                except Exception as chart_err:
                    print(f"[4/5] ⚠ Chart server not available: {chart_err}")
                    print(f"[5/5] Continuing with PMO server only (chart generation disabled)...")
                    print("=" * 60)
                    return await run_with_sessions(query, chat_id, pmo_session, None)
    except Exception as e:
        print(f"[ERROR] MCP connection failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def run_with_sessions(query: str, chat_id: str, pmo_session: ClientSession, chart_session: ClientSession | None):
    """Main logic with access to both PMO and Chart MCP sessions."""
    try:
        # Import re locally to avoid scoping issues with nested functions
        import re
        
        # Tool listing from PMO server
        print("\n[TOOL DISCOVERY] Loading PMO server tools...")
        tools_result = await pmo_session.list_tools()
        tool_count = len(tools_result.tools) if hasattr(tools_result, 'tools') else 0
        print(f"[TOOL DISCOVERY] ✓ Loaded {tool_count} PMO tools")
        
        # Add chart tools if available
        chart_tools_count = 0
        if chart_session:
            print(f"[TOOL DISCOVERY] Loading Chart server tools...")
            chart_tools_result = await chart_session.list_tools()
            chart_tools_count = len(chart_tools_result.tools) if hasattr(chart_tools_result, 'tools') else 0
            print(f"[TOOL DISCOVERY] ✓ Loaded {chart_tools_count} Chart tools")
            print(f"Available Chart tools: {chart_tools_count} tools loaded")

        # Build a rich, structured description of available tools including parameter names/types
        tool_lines = []
        # PMO tools
        for tool in tools_result.tools:
            desc = (getattr(tool, 'description', '') or '').strip().replace('\n', ' ')
            schema = getattr(tool, 'inputSchema', None) or {}
            props = schema.get('properties', {}) if isinstance(schema, dict) else {}
            required = schema.get('required', []) if isinstance(schema, dict) else []
            params = []
            for k, v in (props.items() if isinstance(props, dict) else []):
                ptype = ''
                if isinstance(v, dict):
                    ptype = v.get('type') or v.get('title') or ''
                params.append("{}{}".format(k, (' (' + str(ptype) + ')') if ptype else ''))
            param_str = ", ".join(params) if params else "no parameters"
            req_str = (" Required: {}.".format(', '.join(required))) if required else ""
            tool_lines.append("- {}: {} Params: {}.{}".format(tool.name, desc, param_str, req_str))
        
        # Add chart tools if chart session is available
        if chart_session:
            print("Adding chart tools to available tools list...")
            for tool in chart_tools_result.tools:
                desc = (getattr(tool, 'description', '') or '').strip().replace('\n', ' ')
                schema = getattr(tool, 'inputSchema', None) or {}
                props = schema.get('properties', {}) if isinstance(schema, dict) else {}
                required = schema.get('required', []) if isinstance(schema, dict) else []
                params = []
                for k, v in (props.items() if isinstance(props, dict) else []):
                    ptype = ''
                    if isinstance(v, dict):
                        ptype = v.get('type') or v.get('title') or ''
                    params.append("{}{}".format(k, (' (' + str(ptype) + ')') if ptype else ''))
                param_str = ", ".join(params) if params else "no parameters"
                req_str = (" Required: {}.".format(', '.join(required))) if required else ""
                tool_lines.append("- {}: {} Params: {}.{}".format(tool.name, desc, param_str, req_str))
        
        tool_descriptions = "\n".join(tool_lines)
        print(f"Total tools available: {len(tool_lines)} ({tool_count} PMO + {chart_tools_count} Chart)")

        # Adjust chart generation instructions based on whether chart server is available
        if chart_session:
            chart_instructions = (
                "- CHART GENERATION:\n"
                "  * **ONLY generate charts when user EXPLICITLY requests visualization** with keywords: 'chart', 'graph', 'plot', 'visualize', 'render', 'show chart'\n"
                "  * DO NOT generate charts for: 'show data', 'provide data', 'get data', 'list' - return text/tables instead\n"
                "  * **CRITICAL**: When generating charts, you MUST call the render_chart_from_dataset MCP tool from the D3-Charts server\n"
                "  * **DO NOT** generate HTML directly - the chart server will create professional D3.js charts with data labels and tooltips\n"
                "  * **Tool Call Format**: Return JSON tool call as first thing in response:\n"
                "    {\"tool\":\"render_chart_from_dataset\", \"arguments\": {\"title\": \"Chart Title\", \"data\": {...}, \"chart_type\": \"line\", \"framework\": \"d3\"}}\n"
                "  * **Framework Selection**:\n"
                "    - User says 'use Chart.js', 'with chartjs', 'chartjs' = Pass framework='chartjs' in tool call\n"
                "    - User says 'use D3', 'with D3.js', 'd3 chart', 'pure D3' = Pass framework='d3' in tool call\n"
                "    - No framework specified = Use framework='d3' (default - server automatically selects best renderer)\n"
                "    - Note: The chart server may use Chart.js library as a fallback for better browser compatibility\n"
                "  * **Chart Type Selection**:\n"
                "    - Time series data = chart_type='line'\n"
                "    - Comparisons = chart_type='bar' or 'grouped_bar'\n"
                "    - Proportions = chart_type='pie' or 'donut'\n"
                "    - Correlations = chart_type='scatter' or 'bubble'\n"
                "    - Distributions = chart_type='histogram'\n"
                "  * **Data Format**: Pass data in Chart.js format:\n"
                "    {\"labels\": [\"Q1\", \"Q2\", \"Q3\"], \"datasets\": [{\"label\": \"Series 1\", \"data\": [100, 150, 200], \"backgroundColor\": \"#1f77b4\"}]}\n"
                "  * **Multi-line Resource Charts**: Include 4 series (Capacity, Planned, Actual, Available)\n"
                "  * The chart server will automatically add data labels and interactive tooltips to all charts\n"
            )
        else:
            chart_instructions = (
                "- CHART GENERATION:\n"
                "  * **CHART TOOLS NOT AVAILABLE** - The chart MCP server is not connected to this client\n"
                "  * When user requests charts, inform them that chart generation is currently unavailable\n"
                "  * You can provide the data in table format or JSON format instead\n"
                "  * Suggest they can visualize the data using external tools\n"
            )

        system_instructions = (
            "You are a PMO assistant connected to a PMO MCP server.\n"
            "Rules:\n"
            "- CRITICAL: Before making any tool calls, ALWAYS first check if the required data already exists in the conversation history from previous tool outputs.\n"
            "- If the information is available in recent conversation history (like previous tool outputs), answer directly using that data without making new tool calls.\n"
            "- Only make tool calls when the required data is NOT available in the conversation history or when the user explicitly requests fresh/updated data.\n"
            "- For any question requiring NEW factual project or resource data (not available in conversation), you MUST return a JSON tool call as the very first thing in your response.\n"
            "- If the user request requires more than one MCP tool call (for example: data for multiple resource ids, or multiple independent time ranges), you MUST return a JSON object whose first property is 'plan' and whose value is a list of step objects. Each step object must include an 'id' (short string), 'tool' (tool name), and 'arguments' (object). Do NOT put any explanatory text before the JSON plan.\n"
            "- The JSON must be a single object in this exact form with no leading text: {\"tool\":\"<tool_name>\", \"arguments\": {...}} or when multiple steps are required: {\"plan\": [{\"id\":\"s1\", \"tool\":\"<tool_name>\", \"arguments\": {...}}, ...]}\n"
            "- If clarification is required, ask a short clarifying question instead of guessing data.\n\n"
            "- Important: When the user asks follow-up questions about data that was already retrieved in the conversation (like asking for names after getting IDs), use the existing data instead of making new tool calls.\n"
            f"{chart_instructions}"
            "- EFFICIENCY: Use filtering tools when possible instead of getting all data:\n"
            "  * For portfolio filtering: use get_projects_by_portfolio_and_product_line() with strategic_portfolio parameter\n"
            "  * For complex filtering: use get_projects_dynamic_filter() with filters array\n"
            "  * For resource filtering: combine get_all_resources() data with portfolio info\n"
            "- Portfolio filter examples: 'Market & Sell', 'Auto Insights', 'Plan & Build', 'Vehicles In Use'\n"
            "- Project status examples: 'Active', 'Completed', 'On Hold', 'Cancelled'\n"
            "- Technology project flag: 'YES' or 'NO'\n\n"
            "Available tools and their parameters:\n"
        ) + tool_descriptions + (
            "\n\nExamples:\n"
            "Scenario 1 - New data needed:\n"
            "User: \"List all projects in the PMO system.\"\n"
            "Assistant:\n"
            "{\"tool\":\"get_all_projects\",\"arguments\":{}}\n\n"
            "Scenario 2 - Data already available in conversation:\n"
            "Previous conversation shows resource data was retrieved.\n"
            "User: \"What is the name of resource ID 2?\"\n"
            "Assistant: Based on the resource data retrieved earlier, resource ID 2 is [name from previous data].\n\n"
            "If a user asks for data that requires multiple independent MCP calls (for example: 'Give me monthly hours for resource id 1 and resource id 2 for 2025'), return a plan like this as your FIRST output. The client will execute each plan step in order and append their outputs back into the conversation for you to reason on and then request rendering.\n"
            "Example multi-step plan (fetch-only):\n"
            "{\"plan\":[{\"id\":\"s1\",\"tool\":\"get_resource_allocation_planned_actual\",\"arguments\":{\"resource_id\":1,\"start_date\":\"2025-01-01\",\"end_date\":\"2025-12-31\",\"interval\":\"Monthly\"}},{\"id\":\"s2\",\"tool\":\"get_resource_allocation_planned_actual\",\"arguments\":{\"resource_id\":2,\"start_date\":\"2025-01-01\",\"end_date\":\"2025-12-31\",\"interval\":\"Monthly\"}}]}\n\n"
            "After the client runs the plan steps it will append the tool outputs into the conversation as user messages tagged like '[TOOL OUTPUT - s1]' and '[TOOL OUTPUT - s2]'. When you receive those, produce either a render tool call (e.g., {\"tool\":\"render_from_dataset\", \"arguments\":{...}}) or a final JSON chart payload (labels/datasets) to be forwarded to the renderer.\n\n"
            "User: \"Show planned vs actual hours for resource 42 from 2025-01-01 to 2025-12-31 monthly.\"\n"
            "Assistant:\n"
            "{\"tool\":\"get_resource_allocation_planned_actual\",\"arguments\":{\"resource_id\":42,\"start_date\":\"2025-01-01\",\"end_date\":\"2025-12-31\",\"interval\":\"Monthly\"}}\n\n"
            "User: \"Give me projects in Market & Sell portfolio with hours and costs.\"\n"
            "Assistant:\n"
            "{\"tool\":\"get_projects_by_portfolio_and_product_line\",\"arguments\":{\"strategic_portfolio\":\"Market & Sell\"}}\n\n"
            "User: \"Show me all resources in Market & Sell portfolio.\"\n"
            "Assistant:\n"
            "{\"tool\":\"get_projects_dynamic_filter\",\"arguments\":{\"filters\":[{\"column\":\"strategic_portfolio\",\"operator\":\"=\",\"value\":\"Market & Sell\"}],\"logical_operator\":\"AND\",\"fields\":[\"project_name\",\"strategic_portfolio\",\"product_line\",\"project_status\"]}}\n\n"
            "User: \"Filter projects by technology flag and active status.\"\n"
            "Assistant:\n"
            "{\"tool\":\"get_projects_dynamic_filter\",\"arguments\":{\"filters\":[{\"column\":\"technology_project\",\"operator\":\"=\",\"value\":\"YES\"},{\"column\":\"project_status\",\"operator\":\"=\",\"value\":\"Active\"}],\"logical_operator\":\"AND\",\"fields\":[\"project_name\",\"technology_project\",\"project_status\",\"strategic_portfolio\"]}}\n\n"
            "Scenario 3 - Chart generation (after data is retrieved):\n"
            "User has requested data and now asks: \"Show this as a chart\" or \"Render in d3.js\"\n"
            "Assistant:\n"
            "{\"tool\":\"render_chart_from_dataset\",\"arguments\":{\"title\":\"Resource Hours - Q1 2025\",\"data\":{\"labels\":[\"Jan\",\"Feb\",\"Mar\"],\"datasets\":[{\"label\":\"Planned\",\"data\":[160,152,168],\"backgroundColor\":\"#1f77b4\"},{\"label\":\"Actual\",\"data\":[155,148,165],\"backgroundColor\":\"#ff7f0e\"}]},\"chart_type\":\"line\",\"framework\":\"d3\"}}\n\n"
            "If you need to provide commentary or explanation, put it AFTER the JSON object. The client will execute the first JSON object it finds and then provide the tool output back to you for any further reasoning.\n"
        )

        system_messages = [
            {"role": "system", "content": system_instructions}
        ]

        # Build a richer system context by injecting resources and prompts from the MCP server
        resources_result = await pmo_session.list_resources()
        prompts_result = await pmo_session.list_prompts()
        resources = getattr(resources_result, 'resources', [])
        prompts = getattr(prompts_result, 'prompts', [])

        # Inject resource and prompt contents into the system context so Claude can use them
        for resource in resources:
            content = getattr(resource, 'content', None) or getattr(resource, '_content', None)
            if isinstance(content, str) and content.strip():
                system_messages.append({"role": "system", "content": f"[{resource.name}] {content}"})
        for prompt in prompts:
            content = getattr(prompt, 'content', None) or getattr(prompt, '_content', None)
            if isinstance(content, str) and content.strip():
                system_messages.append({"role": "system", "content": f"[{prompt.name}] {content}"})

        # Prepare the initial user message
        user_message = {"role": "user", "content": query}
        
        print("\n" + "=" * 60)
        print(f"[USER QUERY] {query}")
        print("=" * 60)

        # Load or initialize short-lived in-process conversation memory for this chat_id
        conversation_messages = load_chat_memory(chat_id).copy() if load_chat_memory(chat_id) else []
        if not isinstance(conversation_messages, list):
            conversation_messages = []
        print(f"[MEMORY] Loaded {len(conversation_messages)} previous messages from chat history")
        # Append the new user message as the latest turn and persist immediately
        conversation_messages.append(user_message)
        # Persist right away so a chat file exists for this chat_id even before assistant returns
        try:
            set_chat_memory(chat_id, conversation_messages)
        except Exception:
            pass

        # Build a single string system_text from system_messages for Anthropic calls
        system_text = "\n".join([m['content'] for m in system_messages])

        # Helper: if assistant returns full HTML (chart), save to html-charts/ and return filepath

        def save_chartjs_json_if_needed(text: str, query_text: str = None) -> str | None:
            """If `text` contains Chart.js JSON data, extract it and create an HTML chart."""
            if not text:
                return None
            
            try:
                # Look for JSON code blocks that contain Chart.js data
                json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
                json_matches = re.findall(json_pattern, text, re.DOTALL | re.IGNORECASE)
                
                for json_text in json_matches:
                    try:
                        chart_data = json.loads(json_text.strip())

                        # Check if this looks like Chart.js data
                        if (isinstance(chart_data, dict) and
                            chart_data.get('type') in ['line', 'bar', 'pie', 'doughnut', 'radar', 'polarArea'] and
                            'data' in chart_data):

                            # Create Chart.js HTML
                            chart_title = query_text or "Chart"

                            payload = {
                                "tool": "render_from_dataset",
                                "arguments": {
                                    "title": chart_title,
                                    "data": chart_data,
                                    "chart_type": chart_data.get('type', 'line')
                                }
                            }

                            # DISABLED: Auto-chart generation disabled
                            print("📊 Chart generation disabled - use :chart command if needed")
                            return None
                    except json.JSONDecodeError:
                        continue

                return None
                
            except Exception as e:
                print(f"Chart JSON detection error: {e}")
                return None

        def save_html_response_if_needed(text: str, query_text: str = None, prefix: str = "chart") -> str | None:
            """If `text` looks like a full HTML document or a complete chart page, save it to html-charts and return path.
            This function extracts only the HTML content, removing explanatory text before/after the HTML.
            """
            markers = ["<!DOCTYPE html", "<html", "<script id=\"chart-data\"", "<div id=\"chart\""]
            if not any(m in (text or '') for m in markers):
                return None
                    
            # Extract only the HTML content, removing explanatory text
            html_content = text
            try:
                # Find the start of HTML (either <!DOCTYPE html or <html)
                start_match = re.search(r'<!DOCTYPE\s+html[^>]*>|<html[^>]*>', text, re.IGNORECASE | re.DOTALL)
                if start_match:
                    start_pos = start_match.start()
                    # Find the end of HTML (</html>)
                    end_match = re.search(r'</html\s*>', text[start_pos:], re.IGNORECASE)
                    if end_match:
                        end_pos = start_pos + end_match.end()
                        html_content = text[start_pos:end_pos]
                        print(f"Extracted clean HTML: {len(html_content)} chars (was {len(text)} chars)")
                    else:
                        print("Warning: Found HTML start but no </html> tag, using full text")
                else:
                    print("Warning: HTML markers found but no DOCTYPE/html tag, using full text")
            except Exception as e:
                print(f"Warning: HTML extraction failed: {e}, using full text")
                    
            try:
                outdir = Path(__file__).resolve().parent / "html-charts"
                outdir.mkdir(parents=True, exist_ok=True)
                slug = ""
                if query_text:
                    slug = re.sub(r'[^A-Za-z0-9_-]', '_', query_text)[:40]
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                h = hashlib.sha1((html_content or '').encode('utf-8')).hexdigest()[:6]
                filename = f"{prefix}_{slug}_{ts}_{h}.html" if slug else f"{prefix}_{ts}_{h}.html"
                filepath = outdir / filename
                with open(filepath, 'wb') as f:
                    data = (html_content or '').encode('utf-8')
                    f.write(data)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
                return str(filepath)
            except Exception as e:
                print("Failed to save HTML to file:", e)
                return None

                # Automatic chart generation: if the user asked for a chart and we have recent tool output, spawn the chart generator
        async def try_auto_generate_chart_from_last_tool_output(user_query: str):
            nonlocal conversation_messages
            # Detect chart intent
            if not re.search(r"\b(chart|plot|render|visuali[sz]e|graph)\b", user_query, re.IGNORECASE):
                return None
            # Find the most recent TOOL OUTPUT block in conversation_messages (any role)
            last_tool_data = None
            last_tool_name = None
            for msg in reversed(conversation_messages):
                content = msg.get('content') if isinstance(msg.get('content'), str) else None
                if not content:
                    continue
                # Accept lines that begin with [TOOL OUTPUT - NAME] or similar markers
                header_match = re.match(r"\[TOOL OUTPUT - ([^\]]+)\]\s*(.*)$", content, re.DOTALL)
                if header_match:
                    last_tool_name = header_match.group(1)
                    last_tool_data = header_match.group(2).strip()
                    break
                # Sometimes the tool output is embedded as JSON only; accept a JSON object or array on its own line
                stripped = content.strip()
                if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                    # Heuristic: treat this as the latest tool output
                    last_tool_data = stripped
                    # no tool name available in this case
                    last_tool_name = None
                    break
            if not last_tool_data:
                return None

            # Helper: try to parse the last tool payload into usable records
            def parse_tool_payload(payload: str):
                if not payload or not isinstance(payload, str):
                    return None
                text = payload.strip()
                # Detect a Markdown-style table and convert to list-of-dicts
                # Example header: | # | Project Name | Product Line | Total Planned Cost |
                lines = text.splitlines()
                tbl_start = None
                for i in range(len(lines)-1):
                    # a header line with '|' followed by a separator like |---| or ---
                    if '|' in lines[i] and re.search(r"\|?\s*-{3,}\s*\|?", lines[i+1]):
                        tbl_start = i
                        break
                if tbl_start is not None:
                    try:
                        header_line = lines[tbl_start]
                        # gather subsequent table rows
                        data_rows = []
                        for r in lines[tbl_start+2:]:
                            if not r.strip() or '|' not in r:
                                break
                            data_rows.append(r)
                        def split_row(r):
                            return [c.strip() for c in re.split(r"\s*\|\s*", r.strip().strip('|'))]
                        headers = split_row(header_line)
                        parsed = []
                        for dr in data_rows:
                            cells = split_row(dr)
                            while len(cells) < len(headers):
                                cells.append('')
                            row = {}
                            for h, c in zip(headers, cells):
                                v = c
                                # try to parse currency/number
                                num = None
                                try:
                                    s = re.sub(r'[^0-9.\-]', '', v)
                                    if s not in ('', '-', None):
                                        num = float(s)
                                except Exception:
                                    num = None
                                row[h or 'col'] = (num if num is not None else v)
                            parsed.append(row)
                        if parsed:
                            return parsed
                    except Exception:
                        pass
                # If it's fenced JSON, extract inner
                m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
                if m:
                    text = m.group(1).strip()
                # Sometimes tool output is a quoted JSON string (double-encoded). Try to detect and unquote
                if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
                    try:
                        unq = json.loads(text)
                        if isinstance(unq, (dict, list)):
                            return unq
                        text = unq if isinstance(unq, str) else text
                    except Exception:
                        # fall through
                        pass
                # Direct parse attempt
                try:
                    return json.loads(text)
                except Exception:
                    # Try to extract first {...} or [...] block
                    start = text.find('{')
                    if start == -1:
                        start = text.find('[')
                    end = text.rfind('}')
                    if end == -1:
                        end = text.rfind(']')
                    if start != -1 and end != -1 and end > start:
                        candidate = text[start:end+1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            # Try cleaning trailing commas
                            cleaned = re.sub(r',\s*(?=[\]\}])', '', candidate)
                            try:
                                return json.loads(cleaned)
                            except Exception:
                                return None
                return None

            # Instead of only using the last tool output, prefer using an LLM-based matcher
            # that examines all cached tool outputs in the conversation and selects the
            # one that best answers the user's query. If none match, ask the client to
            # fetch the data live from the MCP server.

            # Collect all tool outputs from the conversation into a list with their message index
            cached_tool_outputs = []  # list of {msg_index, name, content}
            for mi, msg in enumerate(conversation_messages):
                content = msg.get('content') if isinstance(msg.get('content'), str) else None
                if not content:
                    continue
                header_match = re.match(r"\[TOOL OUTPUT - ([^\]]+)\]\s*(.*)$", content, re.DOTALL)
                if header_match:
                    cached_tool_outputs.append({'msg_index': mi, 'name': header_match.group(1), 'content': header_match.group(2).strip()})
                    continue
                # raw JSON-only user messages may also contain tool outputs
                stripped = content.strip()
                if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                    cached_tool_outputs.append({'msg_index': mi, 'name': None, 'content': stripped})

            # If the user explicitly mentioned a resource id, try a deterministic match first:
            requested_ids = []
            try:
                ids1 = re.findall(r"resource[_\s]*id\s*[:=]?\s*(\d+)", user_query, re.IGNORECASE)
                ids2 = re.findall(r"resource\s+(\d+)\b", user_query, re.IGNORECASE)
                for x in ids1 + ids2:
                    try:
                        requested_ids.append(int(x))
                    except Exception:
                        pass
            except Exception:
                requested_ids = []

            # Initialize selection variables to avoid UnboundLocalError in all branches
            # Note: do NOT reinitialize selection here â€” keep any deterministic
            # match found above. The matcher logic below will only set these
            # if it returns an explicit choice or requests a fetch.

            # Initialize selection variables and deterministic hit flag
            selected_payload = None
            selected_name = None
            deterministic_hit = False

            # Deterministic matching: for each cached output, look backward a few messages
            # to find the assistant tool-call JSON that produced it, then compare arguments.resource_id
            if requested_ids and cached_tool_outputs:
                for entry in reversed(cached_tool_outputs):
                    midx = entry.get('msg_index')
                    if midx is None:
                        continue
                    # look back up to 6 messages for an assistant message that contains the JSON tool call
                    for lookback in range(1, 3):
                        i = midx - lookback
                        if i < 0:
                            break
                        mmsg = conversation_messages[i]
                        mcontent = mmsg.get('content') if isinstance(mmsg.get('content'), str) else None
                        if not mcontent:
                            continue
                        # find fenced JSON blocks or inline JSON
                        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", mcontent, re.IGNORECASE)
                        parsed_call = None
                        if m:
                            try:
                                parsed_call = json.loads(m.group(1))
                            except Exception:
                                parsed_call = None
                        else:
                            inline = re.search(r"(\{\s*\"tool\"[\s\S]*?\})", mcontent)
                            if inline:
                                try:
                                    parsed_call = json.loads(inline.group(1))
                                except Exception:
                                    parsed_call = None
                        if not parsed_call or not isinstance(parsed_call, dict):
                            continue
                        args = parsed_call.get('arguments', {}) or {}
                        rid = args.get('resource_id') or args.get('resourceId') or args.get('resource')
                        try:
                            if isinstance(rid, str) and rid.isdigit():
                                rid = int(rid)
                        except Exception:
                            pass
                        if isinstance(rid, int) and rid in requested_ids:
                            # deterministic hit
                            selected_name = entry.get('name')
                            selected_payload = entry.get('content')
                            deterministic_hit = True
                            break
                    if selected_payload:
                        break

            # If deterministic match found, skip the LLM matcher and use the selected payload.
            # The assistant should return a JSON object exactly in one of these forms:
            # {"match_index": N}  -> use cached_tool_outputs[N]
            # {"fetch": {"tool": "get_resource_allocation_planned_actual", "arguments": { ... } }} -> client will fetch
            # {"none": true} -> no suitable data found and no fetch requested
            # If no deterministic match was found above, ask the matcher LLM to pick
            matcher_json = None
            if not deterministic_hit:
                matcher_request = {
            'user_query': user_query,
            'cached_count': len(cached_tool_outputs),
                }

                matcher_prompt = (
            "You are a small helper that chooses whether a user's chart request can be satisfied from cached tool outputs.\n"
            "Input: a user query and a numbered list (0..N-1) of cached tool outputs (each is JSON or text).\n"
            "Task: If one of the cached tool outputs contains the data needed to fulfill the user's query, return exactly {\"match_index\": <index>} where <index> is the zero-based index into the list.\n"
            "If none of the cached outputs are suitable, return exactly {\"fetch\": {\"tool\": \"get_resource_allocation_planned_actual\", \"arguments\": {\"resource_id\": <id>, \"start_date\": \"YYYY-MM-DD\", \"end_date\": \"YYYY-MM-DD\", \"interval\": \"Monthly\"}}} when the query appears to request resource allocation data for a specific resource, choosing sensible dates (default to current year) and a single resource id inferred from the query.\n"
            "If unsure and no fetch should be made, return exactly {\"none\": true}.\n"
            "Return only JSON in one of the three forms above, with no extra text.\n"
                )

                # prepare the list items for the prompt (truncate items to avoid blowing tokens)
                preview_items = []
                for i, item in enumerate(cached_tool_outputs):
                    c = item.get('content') or ''
                    preview = c[:1000].replace('\n', '\\n')
                    preview_items.append(f"{i}: {preview}")

                full_prompt = matcher_prompt + "\nUser query:\n" + user_query + "\n\nCached tool outputs (index: preview):\n" + "\n".join(preview_items)

                # Call the configured Bedrock model synchronously to get the match instruction
                matcher_response_text = None
                try:
                    matcher_response_text = call_bedrock(system_text, [{"role": "user", "content": full_prompt}], max_tokens=300, model=BEDROCK_MODEL)
                except Exception as e:
                    print('Matcher LLM call failed, falling back to last-tool behavior:', e)
                    matcher_response_text = None

                # Helper to parse JSON from the matcher response
                def parse_json_response(text: str):
                    if not text:
                        return None
                    # try direct parse or fenced JSON
                    try:
                        return json.loads(text)
                    except Exception:
                        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
                        if m:
                            try:
                                return json.loads(m.group(1))
                            except Exception:
                                pass
                        # extract first {...}
                        start = text.find('{')
                        end = text.rfind('}')
                        if start != -1 and end != -1 and end > start:
                            try:
                                return json.loads(text[start:end+1])
                            except Exception:
                                pass
                    return None

                matcher_json = parse_json_response(matcher_response_text) if matcher_response_text else None

            # Do not reinitialize selected_payload/selected_name here â€" deterministic hit
            # may have already populated them above.
            # If the matcher returned a match_index, use that cached payload
            if matcher_json and isinstance(matcher_json, dict) and 'match_index' in matcher_json:
                idx = int(matcher_json.get('match_index'))
                if 0 <= idx < len(cached_tool_outputs):
                    selected_name = cached_tool_outputs[idx].get('name')
                    selected_payload = cached_tool_outputs[idx].get('content')

            # If matcher asked to fetch, call the MCP tool
            elif matcher_json and isinstance(matcher_json, dict) and 'fetch' in matcher_json:
                fetch = matcher_json.get('fetch') or {}
                tool_to_call = fetch.get('tool')
                args = fetch.get('arguments', {}) or {}
                try:
                    print(f"Matcher requested fetch: {tool_to_call} {args}")
                    tool_result = await pmo_session.call_tool(tool_to_call, args)
                    # normalize tool_result into a string payload
                    try:
                        if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                            result_content = json.dumps(tool_result.structuredContent, default=str)
                        elif hasattr(tool_result, 'content') and tool_result.content is not None:
                            content = tool_result.content
                            if isinstance(content, list):
                                parts = [getattr(p, 'text', p) for p in content]
                                if len(parts) == 1 and isinstance(parts[0], str):
                                    try:
                                        parsed_payload = json.loads(parts[0])
                                        result_content = json.dumps(parsed_payload, default=str)
                                    except Exception:
                                        result_content = parts[0]
                                else:
                                    try:
                                        result_content = json.dumps(parts, default=str)
                                    except Exception:
                                        result_content = "\n".join(str(p) for p in parts)
                            else:
                                if isinstance(content, (dict, list)):
                                    result_content = json.dumps(content, default=str)
                                else:
                                    result_content = str(content)
                        else:
                            try:
                                result_content = json.dumps(tool_result, default=str)
                            except Exception:
                                result_content = str(tool_result)
                    except Exception:
                        result_content = None
                    if result_content:
                        # append tool output into conversation and use it
                        conversation_messages.append({"role": "user", "content": f"[TOOL OUTPUT - {tool_to_call}]\n{result_content}"})
                        if len(conversation_messages) > MEMORY_MAX_MESSAGES:
                            conversation_messages = conversation_messages[-MEMORY_MAX_MESSAGES:]
                        set_chat_memory(chat_id, conversation_messages)
                        selected_name = tool_to_call
                        selected_payload = result_content
                except Exception as e:
                    print('Live fetch failed:', e)

            # If matcher didn't return anything usable, fall back to using the most recent cached payload
            if not selected_payload and cached_tool_outputs:
                selected_name = cached_tool_outputs[-1].get('name')
                selected_payload = cached_tool_outputs[-1].get('content')

            if not selected_payload:
                return None

            dataset_obj = parse_tool_payload(selected_payload)
            # Fallback: if payload looks like an HTML fragment containing a <script id='chart-data'> JSON, extract it
            if not dataset_obj and isinstance(selected_payload, str):
                mscript = re.search(r"<script[^>]*id=['\"]chart-data['\"][^>]*>([\s\S]*?)</script>", selected_payload, re.IGNORECASE)
                if mscript:
                    inner = mscript.group(1).strip()
                    try:
                        dataset_obj = json.loads(inner)
                    except Exception:
                        try:
                            cleaned = re.sub(r',\s*(?=[\]}])', '', inner)
                            dataset_obj = json.loads(cleaned)
                        except Exception:
                            dataset_obj = None

            if not dataset_obj:
                # Helpful debug message to aid tracing why no dataset was forwarded
                print('No parsable dataset found in selected payload. Sample preview:')
                try:
                    preview = (selected_payload or '')[:1000]
                    print(preview)
                except Exception:
                    print('[unable to preview selected_payload]')
                return None

            # If spawnable failed or produced HTML without embedded data, prefer forwarding the dataset
            # to the centralized D3 MCP server. If that fails, fall back to the HTTP adapter/local renderer.
            try:
                # Detect explicit user request for specific chart types and pass hint to server
                chart_hint = None
                if user_query and re.search(r'\b(donut|doughnut)\b', user_query, re.IGNORECASE):
                    chart_hint = 'donut'
                elif user_query and re.search(r'\b(pie)\b', user_query, re.IGNORECASE):
                    chart_hint = 'pie'
                elif user_query and re.search(r'\b(grouped[\s_-]?bar|multi[\s_-]?bar)\b', user_query, re.IGNORECASE):
                    chart_hint = 'grouped_bar'
                elif user_query and re.search(r'\b(stacked[\s_-]?bar)\b', user_query, re.IGNORECASE):
                    chart_hint = 'stacked_bar'
                elif user_query and re.search(r'\b(horizontal[\s_-]?bar)\b', user_query, re.IGNORECASE):
                    chart_hint = 'horizontal_bar'
                elif user_query and re.search(r'\b(bar)\b', user_query, re.IGNORECASE):
                    chart_hint = 'bar'
                elif user_query and re.search(r'\b(line)\b', user_query, re.IGNORECASE):
                    chart_hint = 'line'

                # The D3 MCP server expects a tool-like object; forward the payload and include chart_type hint
                # Debug: show what will be forwarded to D3 MCP
                # Debug: Dataset preview (commented for cleaner output)
                # try:
                #     preview = None
                #     if isinstance(dataset_obj, (dict, list)):
                #         preview = json.dumps(dataset_obj)[:1000]
                #     else:
                #         preview = str(dataset_obj)[:1000]
                # except Exception:
                #     preview = '<unserializable dataset>'
                # print(f'ðŸ“Š Forwarding chart to D3 MCP (type: {chart_hint})')  # Debug: commented for cleaner output
                        
                # Check if cached data is appropriate for the requested chart type
                # If user is asking for project-based charts but we have monthly aggregate data, skip auto-chart
                project_chart_request = chart_hint in ['bar'] and user_query and re.search(r'\b(project|each project)\b', user_query, re.IGNORECASE)
                has_temporal_data = isinstance(dataset_obj, dict) and 'result' in dataset_obj and isinstance(dataset_obj['result'], list) and dataset_obj['result']
                has_project_details = isinstance(dataset_obj, dict) and 'result' in dataset_obj and isinstance(dataset_obj['result'], list) and dataset_obj['result'] and 'project_allocation_details' in dataset_obj['result'][0]
                        
                if project_chart_request and has_temporal_data and not has_project_details:
                    print('Cached data may not be appropriate for project-based chart - skipping auto-chart')
                    return None

                # Normalize wrapper shapes like {"result": [...]} -> use the inner list
                data_to_forward = dataset_obj
                if isinstance(dataset_obj, dict) and 'result' in dataset_obj and isinstance(dataset_obj['result'], list):
                    data_to_forward = dataset_obj['result']
                # Also unwrap single-key dicts where the value is a list (common wrapper)
                if isinstance(data_to_forward, dict):
                    # try to find any list value to use if labels/datasets not present
                    list_vals = [v for v in data_to_forward.values() if isinstance(v, list) and v]
                    if list_vals:
                        data_to_forward = list_vals[0]

                # If we have a list of records, try to synthesize {labels, datasets} for Chart.js
                synthesized = None
                if isinstance(data_to_forward, list) and data_to_forward:
                    # Special handling for grouped_bar with project allocation details
                    if chart_hint == 'grouped_bar' and all(isinstance(r, dict) and 'project_allocation_details' in r for r in data_to_forward):
                        # Extract time periods as labels and projects as separate datasets
                        time_labels = []
                        all_projects = set()

                        # Collect all unique project names and time periods - use first available time field
                        for record in data_to_forward:
                            # Generic time field detection - let the MCP server provide appropriate format
                            time_label = None
                            for field in ['month', 'start_date', 'end_date', 'date', 'period', 'time']:
                                if field in record and record[field]:
                                    time_label = str(record[field])
                                    break
                            if not time_label:
                                time_label = 'Unknown'
                            time_labels.append(time_label)

                            for proj in record.get('project_allocation_details', []):
                                all_projects.add(proj.get('project_name', 'Unknown'))

                        all_projects = sorted(list(all_projects))
                        colors = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f']

                        # Build datasets - one per project
                        datasets = []
                        for i, project_name in enumerate(all_projects):
                            project_data = []
                            for record in data_to_forward:
                                # Find this project's percentage in this month
                                percentage = 0
                                for proj in record.get('project_allocation_details', []):
                                    if proj.get('project_name') == project_name:
                                        percentage = proj.get('planned_percentage', 0)
                                        break
                                project_data.append(percentage)

                            datasets.append({
                                'label': project_name,
                                'data': project_data,
                                'backgroundColor': colors[i % len(colors)],
                                'borderColor': colors[i % len(colors)]
                            })

                        synthesized = {
                            'labels': time_labels,
                            'datasets': datasets
                        }
                    else:
                        # Original single-dataset logic
                        sample = data_to_forward[0]
                        if isinstance(sample, dict):
                            # possible label keys and cost keys
                            label_keys = ['project_name', 'name', 'project', 'title']
                            value_keys = ['project_resource_cost_planned', 'planned_cost', 'total_planned_cost', 'cost', 'project_cost_planned']
                            found_label = None
                            found_value = None
                            for k in label_keys:
                                if k in sample:
                                    found_label = k
                                    break
                            for k in value_keys:
                                if k in sample:
                                    found_value = k
                                    break
                            # fallback: choose first string-like key for labels and first numeric key for values
                            if not found_label:
                                for k, v in sample.items():
                                    if isinstance(v, str) and k.lower().find('name') >= 0:
                                        found_label = k
                                        break
                            if not found_value:
                                for k, v in sample.items():
                                    if isinstance(v, (int, float)):
                                        found_value = k
                                        break

                            if found_label and found_value:
                                labels = []
                                values = []
                                for rec in data_to_forward:
                                    lbl = rec.get(found_label) if isinstance(rec, dict) else str(rec)
                                    val = rec.get(found_value) if isinstance(rec, dict) else None
                                    # coerce numeric strings to numbers
                                    if isinstance(val, str):
                                        try:
                                            val = float(re.sub(r'[^0-9.\-]', '', val))
                                        except Exception:
                                            val = 0.0
                                    if val is None:
                                        try:
                                            # try nested lookup like rec['fields']['project_resource_cost_planned']
                                            val = float(re.sub(r'[^0-9.\-]', '', str(rec.get(found_value, 0))))
                                        except Exception:
                                            val = 0.0
                                    labels.append(str(lbl))
                                    values.append(float(val or 0))

                                # Provide simple colors for slices
                                colors = [
                                    '#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f'
                                ]
                                bg = [colors[i % len(colors)] for i in range(len(values))]
                                synthesized = {
                                    'labels': labels,
                                    'datasets': [{
                                        'label': 'Planned Cost',
                                        'data': values,
                                        'backgroundColor': bg,
                                        'borderColor': bg,
                                        'borderWidth': 1
                                    }]
                                }
                            else:
                                # fallback to original format
                                synthesized = {'data': data_to_forward}
                        else:
                            # fallback for non-dict data
                            synthesized = {'data': data_to_forward}

                # Only forward if we have something plausible to render
                if synthesized is not None:
                    payload_data = synthesized
                else:
                    # fallback to forwarding raw data_to_forward if it already looks chart-ready
                    payload_data = data_to_forward

                # Validate payload_data with more flexible criteria
                valid_forward = False
                validation_msg = ""

                if isinstance(payload_data, dict):
                    # Chart.js format: has labels and datasets
                    if payload_data.get('labels') and payload_data.get('datasets'):
                        valid_forward = True
                        validation_msg = "Valid Chart.js format detected"
                    # Chart.js full config: has data.labels and data.datasets
                    elif isinstance(payload_data.get('data'), dict) and payload_data['data'].get('labels') and payload_data['data'].get('datasets'):
                        valid_forward = True
                        validation_msg = "Valid Chart.js config format detected"
                    # Raw data: any non-empty dict with meaningful keys
                    elif len(payload_data) > 0 and any(isinstance(v, (list, dict)) for v in payload_data.values()):
                        valid_forward = True
                        validation_msg = "Valid data structure detected"
                    else:
                        validation_msg = f"Invalid dict format: keys={list(payload_data.keys())}"
                elif isinstance(payload_data, list) and payload_data:
                    valid_forward = True
                    validation_msg = f"Valid list format with {len(payload_data)} items"
                else:
                    validation_msg = f"Invalid data type: {type(payload_data)}"

                if not valid_forward:
                    # Comment out the warning but still skip invalid data
                    # print(f'Skipping chart generation: {validation_msg}')  # Debug: commented for cleaner output
                    return None

                # Chart generation via D3 MCP disabled - charts are now generated inline by AI
                print("[NOTE] Chart generation delegated to AI inline HTML generation")
            except Exception as e:
                print("Chart configuration error:", e)

        # If D3 delegation did not succeed, continue with previous adapter-based fallback
        html_output = None

        # If this user query appears to request a chart and we have recent tool output, try auto-generate now and return early
        # DISABLED: Auto-chart generation - only generate charts when explicitly requested
        # auto_generated = await try_auto_generate_chart_from_last_tool_output(query)
        # if auto_generated:
        #     return auto_generated

        # Iterative tool-calling loop driven by Claude JSON responses
        max_iterations = 3
        iteration = 0
        last_tool_output = None

        def extract_json_from_text(text: str):
            # Try direct parse, fenced JSON, or first {...} block
            try:
                return json.loads(text)
            except Exception:
                m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
                candidate = None
                if m:
                    candidate = m.group(1)
                else:
                    # Extract the first complete JSON object by counting braces
                    start = text.find('{')
                    if start != -1:
                        brace_count = 0
                        in_string = False
                        escape_next = False
                        
                        for i in range(start, len(text)):
                            char = text[i]
                            
                            if escape_next:
                                escape_next = False
                                continue
                            
                            if char == '\\':
                                escape_next = True
                                continue
                            
                            if char == '"':
                                in_string = not in_string
                                continue
                            
                            if not in_string:
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        candidate = text[start:i+1]
                                        break
                
                if candidate:
                    try:
                        return json.loads(candidate)
                    except Exception:
                        return None
            return None

        # Iterative LLM loop: request -> optional tool call -> feed tool output back -> repeat
        while iteration < max_iterations:
            iteration += 1
            print(f"\n[LLM ITERATION {iteration}/{max_iterations}] Calling {llm_client.config.provider.value.upper()} model...")
            print(f"[LLM] System message length: {len(system_text)} chars")
            print(f"[LLM] Conversation messages: {len(conversation_messages)}")
            try:
                response_text = llm_client.call_llm(system_text, conversation_messages, max_tokens=1000)
                print(f"[LLM] ✓ Response received ({len(response_text)} chars)")
            except Exception as e:
                print(f"[LLM ERROR] {llm_client.config.provider.value.upper()} API error: {e}")
                traceback.print_exc()
                return f"ERROR: {llm_client.config.provider.value.upper()} API request failed: {e}"

            # Extract assistant text
            assistant_text = response_text if isinstance(response_text, str) else str(response_text)

            # Persist the assistant's raw response into the in-memory conversation so subsequent turns see it
            conversation_messages.append({"role": "assistant", "content": assistant_text})
            # Trim memory to limit size
            if len(conversation_messages) > MEMORY_MAX_MESSAGES:
                conversation_messages = conversation_messages[-MEMORY_MAX_MESSAGES:]
            chat_memories[chat_id] = conversation_messages

            # print(f"{llm_client.config.provider.value.upper()} (iteration {iteration}) response:")  # Debug: commented for cleaner output
            # print(assistant_text)  # Debug: commented for cleaner output - full response can be very long
                    
            # Show essential execution status
            response_type = "text response"
            if "```json" in assistant_text or '{"tool"' in assistant_text or '{"plan"' in assistant_text:
                response_type = "JSON tool call"
            print(f"{llm_client.config.provider.value.upper()}: {response_type} received")

            # Try to extract JSON tool call from the assistant text
            parsed = extract_json_from_text(assistant_text)

            # IMPORTANT: Do NOT apply keyword-based fallbacks here. Require the model to
            # emit an explicit JSON object describing the tool call (or a 'plan').
            # This avoids hardcoded heuristics and lets the LLM decide the tool to use.

            # If parsed JSON is a multi-step plan, execute each step sequentially
            if parsed and isinstance(parsed, dict) and 'plan' in parsed and isinstance(parsed.get('plan'), list):
                steps = parsed.get('plan')
                # print(f"Received plan with {len(steps)} steps. Executing sequentially...")  # Debug: commented for cleaner output
                plan_results = {}
                for idx, step in enumerate(steps):
                    try:
                        tool_name = step.get('tool')
                        tool_args = step.get('arguments', {}) or {}

                        # Determine routing
                        is_chart_tool = tool_name.startswith('render_chart') or tool_name.startswith('create_')

                        print(f"\n[PLAN STEP {idx+1}/{len(steps)}] Executing {tool_name}")
                        if is_chart_tool:
                            if chart_session:
                                print(f"[ROUTING] Using Chart MCP server")
                            else:
                                print(f"[ERROR] Chart tool requested but Chart server unavailable")
                                plan_results[step.get('id', f'step_{idx+1}')] = json.dumps({"error": "Chart server not available"})
                                continue
                        else:
                            print(f"[ROUTING] Using PMO MCP server")

                        if tool_args:
                            # Print arguments for debugging but limit size
                            args_str = str(tool_args)
                            if len(args_str) > 200:
                                args_str = args_str[:200] + "..."
                            print(f"[ARGS] {args_str}")

                        try:
                            # Route to appropriate server
                            if is_chart_tool and chart_session:
                                tool_result = await chart_session.call_tool(tool_name, tool_args)
                            else:
                                tool_result = await pmo_session.call_tool(tool_name, tool_args)
                            print(f"[RESULT] ✓ {tool_name} completed successfully")
                        except Exception as tool_err:
                            print(f"[ERROR] {tool_name} execution failed: {tool_err}")
                            tool_result = {"error": str(tool_err)}

                        # Normalize tool_result into a string payload
                        try:
                            if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                                result_content = json.dumps(tool_result.structuredContent, default=str)
                            elif hasattr(tool_result, 'content') and tool_result.content is not None:
                                content = tool_result.content
                                if isinstance(content, list):
                                    parts = []
                                    for p in content:
                                        text = getattr(p, 'text', str(p))
                                        # Apply same Unicode filtering as main tool execution
                                        if isinstance(text, str):
                                            import unicodedata
                                            # Remove emojis and other Unicode symbols
                                            text = ''.join(char for char in text if unicodedata.category(char)[0] != 'S')
                                            # Remove other problematic Unicode characters
                                            text = text.encode('ascii', errors='ignore').decode('ascii')
                                        parts.append(text)

                                    if len(parts) == 1 and isinstance(parts[0], str):
                                        try:
                                            parsed_payload = json.loads(parts[0])
                                            result_content = json.dumps(parsed_payload, default=str)
                                        except Exception:
                                            result_content = parts[0]
                                    else:
                                        try:
                                            result_content = json.dumps(parts, default=str)
                                        except Exception:
                                            result_content = "\n".join(str(p) for p in parts)
                                else:
                                    if isinstance(content, (dict, list)):
                                        result_content = json.dumps(content, default=str)
                                    else:
                                        content_str = str(content)
                                        # Apply Unicode filtering
                                        import unicodedata
                                        content_str = ''.join(char for char in content_str if unicodedata.category(char)[0] != 'S')
                                        result_content = content_str.encode('ascii', errors='ignore').decode('ascii')
                            else:
                                try:
                                    result_content = json.dumps(tool_result, default=str)
                                except Exception:
                                    result_str = str(tool_result)
                                    # Apply Unicode filtering
                                    import unicodedata
                                    result_str = ''.join(char for char in result_str if unicodedata.category(char)[0] != 'S')
                                    result_content = result_str.encode('ascii', errors='ignore').decode('ascii')
                        except Exception:
                            result_str = str(tool_result)
                            # Apply Unicode filtering as fallback
                            import unicodedata
                            result_str = ''.join(char for char in result_str if unicodedata.category(char)[0] != 'S')
                            result_content = result_str.encode('ascii', errors='ignore').decode('ascii')

                        # Store and append to conversation so Claude can see step outputs
                        plan_results_key = tool_name or f"step_{idx+1}"
                        plan_results[plan_results_key] = result_content
                        conversation_messages.append({"role": "user", "content": f"[TOOL OUTPUT - {tool_name}]\n{result_content}"})
                        # Trim and persist memory after each step
                        if len(conversation_messages) > MEMORY_MAX_MESSAGES:
                            conversation_messages = conversation_messages[-MEMORY_MAX_MESSAGES:]
                        chat_memories[chat_id] = conversation_messages
                        # If the tool output is very large, save it to disk and add a short assistant pointer
                        try:
                            if isinstance(result_content, str) and len(result_content) > 4000:
                                outdir = Path(__file__).resolve().parent / "data-exports"
                                outdir.mkdir(parents=True, exist_ok=True)
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                fname = f"payload_{tool_name}_{chat_id}_{ts}.json"
                                fpath = outdir / fname
                                with open(fpath, 'w', encoding='utf-8') as _f:
                                    _f.write(result_content)
                                conversation_messages.append({"role": "assistant", "content": f"[SAVED_PAYLOAD] {str(fpath)}"})
                                set_chat_memory(chat_id, conversation_messages)
                        except Exception:
                            pass
                    except Exception as e:
                        # print(f"Error while executing plan step {idx+1}: {e}")  # Debug: commented for cleaner output
                        plan_results[f"step_{idx+1}_error"] = str(e)

                # After executing the plan, provide the aggregated outputs back to the loop for further reasoning
                # Try to auto-merge plan step results when they look like time-series for charting
                def try_merge_plan_timeseries(plan_results_dict):
                    # plan_results_dict: {tool_name: result_content (stringified JSON or text)}
                    # Build a list of series with explicit labels and numeric arrays
                    all_series = []
                    labels_union = set()
                    for key, val in plan_results_dict.items():
                        try:
                            parsed = json.loads(val) if isinstance(val, str) else val
                        except Exception:
                            try:
                                parsed = json.loads(str(val))
                            except Exception:
                                parsed = None
                        records = None
                        if isinstance(parsed, dict) and 'result' in parsed and isinstance(parsed['result'], list):
                            records = parsed['result']
                        elif isinstance(parsed, list):
                            records = parsed
                        if not records or not isinstance(records, list):
                            continue
                        # detect label and numeric keys
                        sample = records[0] if records else {}
                        if not isinstance(sample, dict):
                            continue
                        label_key = None
                        for k in sample.keys():
                            if any(x in k.lower() for x in ('month', 'date', 'period', 'time', 'week')):
                                label_key = k; break
                        if not label_key:
                            # fallback to first string-like key
                            for k, v in sample.items():
                                if isinstance(v, str):
                                    label_key = k; break
                        numeric_key = None
                        for k, v in sample.items():
                            if k == label_key:
                                continue
                            if isinstance(v, (int, float)) or (isinstance(v, str) and re.match(r'^[\d,\.\-\s]+$', str(v).strip())):
                                numeric_key = k; break
                        if not label_key or not numeric_key:
                            continue
                        series_labels = [str(r.get(label_key, '')) for r in records]
                        series_values = []
                        for r in records:
                            try:
                                v = r.get(numeric_key, 0)
                                if v is None:
                                    v = 0
                                if isinstance(v, str):
                                    v = float(re.sub(r'[^0-9.\-]', '', v) or 0)
                                series_values.append(float(v))
                            except Exception:
                                series_values.append(0.0)
                        # collect
                        all_series.append({'label': f"{key}:{numeric_key}", 'labels': series_labels, 'data': series_values})
                        for L in series_labels:
                            labels_union.add(L)

                    if not all_series:
                        return None

                    # sort labels: try YYYY-MM detection else lexicographic
                    def sort_labels(lbls):
                        try:
                            if all(re.match(r'^\d{4}-\d{2}$', l) for l in lbls):
                                return sorted(lbls)
                        except Exception:
                            pass
                        return sorted(lbls)

                    unified_labels = sort_labels(list(labels_union))

                    # align each series to unified labels filling missing with 0
                    palette = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b']
                    datasets = []
                    for idx, s in enumerate(all_series):
                        mapping = {l: v for l, v in zip(s['labels'], s['data'])}
                        aligned = [float(mapping.get(L, 0) or 0) for L in unified_labels]
                        color = palette[idx % len(palette)]
                        datasets.append({'label': s['label'], 'data': aligned, 'borderColor': color, 'backgroundColor': color, 'fill': False})

                    return {'labels': unified_labels, 'datasets': datasets}

                merged_payload = None
                try:
                    merged_payload = try_merge_plan_timeseries(plan_results)
                except Exception as _:
                    merged_payload = None

                if merged_payload:
                    # DISABLED: Auto-chart generation for merged plan results
                    print("Auto-chart generation disabled for merged data - use :chart command if needed")
                    last_tool_output = json.dumps(plan_results)
                else:
                    last_tool_output = json.dumps(plan_results)
                # continue to next iteration so Claude gets the tool outputs as user messages
                continue

            # If parsed JSON indicates a tool invocation, execute it
            if parsed and isinstance(parsed, dict) and 'tool' in parsed:
                tool_name = parsed['tool']
                tool_args = parsed.get('arguments', {}) or {}
                        
                # Determine which server to route to
                is_chart_tool = tool_name.startswith('render_chart') or tool_name.startswith('create_')

                # Inject client-side output directory for chart tools
                if is_chart_tool and isinstance(tool_args, dict):
                    # Set the output directory to client's html-charts folder
                    client_chart_dir = Path(__file__).resolve().parent / "html-charts"
                    tool_args['output_dir'] = str(client_chart_dir)
                    print(f"[CHART OUTPUT] Charts will be saved to: {client_chart_dir}")

                if is_chart_tool:
                    if chart_session:
                        print(f"\n[TOOL CALL] Routing to Chart MCP server: {tool_name}")
                    else:
                        print(f"\n[ERROR] Chart tool requested but Chart server unavailable: {tool_name}")
                        conversation_messages.append({"role": "user", "content": f"[ERROR] Chart tool '{tool_name}' requested but Chart server is not connected. Please provide data in table format instead."})
                        continue
                else:
                    print(f"\n[TOOL CALL] Routing to PMO MCP server: {tool_name}")

                if tool_args:
                    # Print arguments for debugging but limit size
                    args_str = str(tool_args)
                    if len(args_str) > 200:
                        args_str = args_str[:200] + "..."
                    print(f"[TOOL ARGS] {args_str}")

                try:
                    # Route to appropriate server
                    if is_chart_tool and chart_session:
                        tool_result = await chart_session.call_tool(tool_name, tool_args)
                    else:
                        tool_result = await pmo_session.call_tool(tool_name, tool_args)
                    print(f"[TOOL RESULT] ✓ {tool_name} completed successfully")
                except Exception as tool_err:
                    print(f"[TOOL ERROR] {tool_name} execution failed: {tool_err}")
                    tool_result = {"error": str(tool_err)}

                # Normalize tool_result into a string payload to send back to Claude
                try:
                    if hasattr(tool_result, 'structuredContent') and tool_result.structuredContent:
                        result_content = json.dumps(tool_result.structuredContent, default=str)
                    elif hasattr(tool_result, 'content') and tool_result.content is not None:
                        content = tool_result.content
                        if isinstance(content, list):
                            parts = []
                            for p in content:
                                text = getattr(p, 'text', str(p))
                                # Handle encoding issues more carefully
                                if isinstance(text, str):
                                    original_length = len(text)
                                    # Only remove specific problematic emojis, not all Unicode
                                    # Remove the specific magnifying glass emoji and similar ones
                                    text = text.replace('\U0001f50d', '[search]')  # ðŸ”
                                    text = text.replace('\U0001f680', '[rocket]')  # ðŸš€
                                    text = text.replace('\U0001f4ca', '[chart]')   # ðŸ“Š
                                    text = text.replace('\U0001f504', '[retry]')   # ðŸ”„
                                    text = text.replace('\u2705', '[check]')      # âœ…
                                    text = text.replace('\u26a0', '[warning]')    # âš ï¸
                                    text = text.replace('\U0001f916', '[robot]')  # ðŸ¤–
                                            
                                    # Only use aggressive filtering if we still have encoding issues
                                    try:
                                        text.encode('utf-8').decode('utf-8')
                                    except UnicodeError:
                                        # Fallback: remove non-ASCII characters but preserve structure
                                        text = text.encode('ascii', errors='replace').decode('ascii')
                                
                                parts.append(text)
                            
                            if len(parts) == 1 and isinstance(parts[0], str):
                                try:
                                    parsed_payload = json.loads(parts[0])
                                    result_content = json.dumps(parsed_payload, default=str)
                                except Exception:
                                    result_content = parts[0]
                            else:
                                try:
                                    result_content = json.dumps(parts, default=str)
                                except Exception:
                                    result_content = "\n".join(str(p) for p in parts)
                        else:
                            if isinstance(content, (dict, list)):
                                result_content = json.dumps(content, default=str)
                            else:
                                result_content = str(content)
                    else:
                        try:
                            result_content = json.dumps(tool_result, default=str)
                        except Exception:
                            result_content = str(tool_result)
                except Exception as e:
                    # print(f"DEBUG: Error processing tool result: {e}")  # Debug: commented for cleaner output
                    result_content = f"Error processing tool result: {str(e)}"

                last_tool_output = result_content
                        
                # Show the tool output to user
                print(f"[TOOL OUTPUT - {tool_name}]")
                print(result_content)
                
                # Check if tool result contains an error - if so, return error to user immediately
                # Don't let LLM try to work around framework/chart type incompatibility errors
                if isinstance(result_content, str):
                    error_indicators = [
                        "Error executing tool",
                        "chart_type_not_supported",
                        "is not supported by Chart.js",
                        "is not supported by D3.js"
                    ]
                    if any(indicator in result_content for indicator in error_indicators):
                        # Extract the actual error message (skip the "Error executing tool" prefix)
                        error_lines = result_content.split('\n')
                        error_message = '\n'.join(line for line in error_lines if line.strip() and not line.startswith('Error executing tool'))
                        
                        conversation_messages.append({"role": "user", "content": f"[TOOL OUTPUT - {tool_name}]\n{result_content}"})
                        conversation_messages.append({"role": "assistant", "content": error_message})
                        set_chat_memory(chat_id, conversation_messages)
                        print(f"\n❌ Tool execution failed - stopping conversation")
                        return error_message
                        
                # Special handling for chart generation tools - auto-open the chart and return immediately
                if tool_name == "render_chart_from_dataset":
                    try:
                        result_dict = json.loads(result_content) if isinstance(result_content, str) else result_content
                        
                        # Extract chart path from various response formats
                        chart_path = None
                        
                        # Format 1: {"status": "ok", "path": "..."}
                        if result_dict.get("status") == "ok" or result_dict.get("status") == "success":
                            chart_path = result_dict.get("path") or result_dict.get("chart_path")
                        
                        # Format 2: {"result": "[DONE] ... chart created: path"}
                        elif "result" in result_dict:
                            result_text = result_dict.get("result", "")
                            if "[DONE]" in result_text and "chart created:" in result_text:
                                # Extract path from "[DONE] Line chart created: D:\...\file.html"
                                import re
                                path_match = re.search(r'chart created:\s*(.+\.html)', result_text)
                                if path_match:
                                    chart_path = path_match.group(1).strip()
                        
                        if chart_path and Path(chart_path).exists():
                            print(f"\n✓ Chart created successfully: {chart_path}")
                            print(f"✓ Opening chart in browser...")
                            try:
                                webbrowser.open(f"file:///{chart_path}")
                            except Exception as browser_err:
                                print(f"Could not auto-open browser: {browser_err}")
                                print(f"Please open manually: {chart_path}")
                            
                            # Persist the successful chart creation and return immediately
                            conversation_messages.append({"role": "user", "content": f"[TOOL OUTPUT - {tool_name}]\n{result_content}"})
                            conversation_messages.append({"role": "assistant", "content": f"Chart created successfully: {chart_path}"})
                            set_chat_memory(chat_id, conversation_messages)
                            return f"Chart created: {chart_path}"
                        elif chart_path:
                            print(f"⚠ Chart file not found at: {chart_path}")
                    except Exception as chart_err:
                        # Not a chart result or couldn't parse, continue normally
                        print(f"[DEBUG] Chart detection error: {chart_err}")
                        pass
                        
                # If the result is an encoding error, provide helpful context
                if "charmap" in result_content and "can't encode character" in result_content:
                    result_content += "\n\nNOTE: This is a PMO server-side encoding issue. The server contains Unicode characters (emojis) that it cannot process. The server administrator needs to clean the data or configure UTF-8 encoding."
                        
                # Append tool output into conversation as a user message so Claude can reason about it in the next turn
                conversation_messages.append({"role": "user", "content": f"[TOOL OUTPUT - {tool_name}]\n{result_content}"})
                # Trim and persist memory after tool output
                if len(conversation_messages) > MEMORY_MAX_MESSAGES:
                    conversation_messages = conversation_messages[-MEMORY_MAX_MESSAGES:]
                set_chat_memory(chat_id, conversation_messages)
                # If the tool output is very large, save it to disk and add a short assistant pointer
                try:
                    if isinstance(result_content, str) and len(result_content) > 4000:
                        outdir = Path(__file__).resolve().parent / "data-exports"
                        outdir.mkdir(parents=True, exist_ok=True)
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        fname = f"payload_{tool_name}_{chat_id}_{ts}.json"
                        fpath = outdir / fname
                        with open(fpath, 'w', encoding='utf-8') as _f:
                            _f.write(result_content)
                        conversation_messages.append({"role": "assistant", "content": f"[SAVED_PAYLOAD] {str(fpath)}"})
                        set_chat_memory(chat_id, conversation_messages)
                except Exception:
                    pass
                # Continue the loop to let Claude decide next action
                continue

            # No tool requested â€” treat assistant_text as final answer
            saved_path = save_html_response_if_needed(assistant_text, query, prefix="claude_answer")
            if saved_path:
                print("Final Claude answer saved to:", saved_path)
                conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {saved_path}"})
                set_chat_memory(chat_id, conversation_messages)
                return f"HTML_SAVED:{saved_path}"
                    
            # DISABLED: Check if Claude provided Chart.js JSON data disabled
            # chart_path = save_chartjs_json_if_needed(assistant_text, query)
            chart_path = None
            if chart_path:
                print("Chart created from Claude's JSON:", chart_path)
                conversation_messages.append({"role": "assistant", "content": f"[HTML_SAVED] {chart_path}"})
                set_chat_memory(chat_id, conversation_messages)
                return f"HTML_SAVED:{chart_path}"
            else:
                # If Claude returned an HTML page but it lacks embedded chart-data, try auto-generating
                # a chart by forwarding the most recent tool output(s) to the centralized D3 MCP server.
                is_html = bool(re.search(r"<!DOCTYPE html|<html", assistant_text, re.IGNORECASE))
                has_embedded = '<script id="chart-data"' in (assistant_text or '')
                recent_tool_output_exists = any(re.search(r"\[TOOL OUTPUT - ", m.get('content', '') or '') for m in conversation_messages)
                if is_html and (not has_embedded) and recent_tool_output_exists:
                    print("Assistant returned HTML without embedded data - attempting to auto-generate chart from recent tool outputs...")
                    try:
                        # Note: Auto-generation already tried earlier in the flow, avoid duplicate chart creation
                        # auto_generated = try_auto_generate_chart_from_last_tool_output(query)  # Debug: commented to avoid duplicate charts
                        # if auto_generated:
                        #     return auto_generated
                        # else:
                        #     print("Auto-generation fallback did not produce an HTML file.")
                        pass
                    except Exception as e:
                        print("Auto-generation fallback failed:", e)

                print("Final answer:")  # Simplified for cleaner output
                print(assistant_text)
                set_chat_memory(chat_id, conversation_messages)
                return assistant_text

                # If we exit loop with last_tool_output, ask Bedrock model to reason over it (final analysis)
                if last_tool_output:
                    system_text = "\n".join([m['content'] for m in system_messages])
                    conversation_messages.append({
                        "role": "user",
                        "content": f"Here is the raw JSON result:\n{last_tool_output}\n\nNow, based on my original query ('{query}'), please compute and explain the answer. Provide only the analysis and final answer."
                    })
                    try:
                        final_text = llm_client.call_llm(system_text, conversation_messages, max_tokens=1000)
                    except Exception as e:
                        print(f'{llm_client.config.provider.value.upper()} reasoning call failed:', e)
                        final_text = f"ERROR: {llm_client.config.provider.value.upper()} reasoning call failed: {e}"
            # If the model produced HTML for the reasoning result, save instead of printing
            saved_path = save_html_response_if_needed(final_text, query, prefix="claude_reasoning")
            if saved_path:
                # DISABLED: Auto-chart generation disabled
                print("Chart generation disabled - use :chart command if needed")
                print("\nModel reasoning result:", final_text)
                conversation_messages.append({"role": "assistant", "content": final_text})
                set_chat_memory(chat_id, conversation_messages)
                return final_text
            else:
                print("\nModel reasoning result:\n")
                print(final_text)
                # Persist final reasoning in memory and return
                conversation_messages.append({"role": "assistant", "content": final_text})
                set_chat_memory(chat_id, conversation_messages)
                return final_text

            # If nothing produced, fallback to previous simple behavior
            print("WARNING: No tool output produced and no final answer returned from model.")
            # Persist current memory state even if no useful output
            set_chat_memory(chat_id, conversation_messages)
            return None

    except Exception as e:
        print("Error during MCP session:")
        traceback.print_exc()

if __name__ == "__main__":
    print(f"Running with {llm_client.config.provider.value.upper()} as the unified LLM client")
    # Start a fresh session id per REPL run unless user chooses to load an existing one
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    # sanitize to match memory_file_for rules
    session_id = re.sub(r'[^A-Za-z0-9_.-]', '_', session_id)[:64]
    current_chat_id = session_id
    # allow starting with a named session via CLI
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--session', '-s', help='Start REPL with this session id (sanitized).')
    known_args, _ = parser.parse_known_args()
    if known_args.session:
        chosen = re.sub(r'[^A-Za-z0-9_.-]', '_', known_args.session)[:64]
        current_chat_id = chosen

    # Ensure chat memory dir exists
    ensure_memory_dir()
    print(f"Session started. Session ID: {current_chat_id}")
    print("Commands: :list-sessions  :use <id>  :show <id>  :show  :provider <name>  :chart  :exit")

    def human_size(n):
        try:
            n = int(n)
        except Exception:
            return str(n)
        for unit in ['B','KB','MB','GB','TB']:
            if n < 1024:
                return f"{n}{unit}"
            n = n/1024
        return f"{n:.1f}TB"

    def list_sessions():
        try:
            files = []
            for p in CHAT_MEMORY_DIR.iterdir():
                if p.is_file() and p.suffix == '.json':
                    stat = p.stat()
                    mtime = datetime.fromtimestamp(stat.st_mtime).isoformat(' ')
                    size = human_size(stat.st_size)
                    files.append((p.name, mtime, size))
            return sorted(files, key=lambda t: t[0])
        except Exception:
            return []

    try:
        # Load (or initialize) memory for this new session so subsequent runs use it
        load_chat_memory(current_chat_id)
        while True:
            try:
                raw = input(f"\n[{current_chat_id}|{llm_client.config.provider.value}] Query: ")
            except EOFError:
                print("\nEOF received, exiting.")
                break
            except KeyboardInterrupt:
                print("\nInterrupted by user.")
                # Save and exit
                try:
                    set_chat_memory(current_chat_id, chat_memories.get(current_chat_id, []))
                except Exception:
                    pass
                break

            if raw is None:
                continue
            query = raw.strip()
            if not query:
                continue
            # REPL commands prefixed with ':'
            if query.startswith(":"):
                parts = query[1:].split()
                cmd = parts[0].lower() if parts else ''
                if cmd in ('exit', 'quit'):
                    print('Exiting.')
                    try:
                        set_chat_memory(current_chat_id, chat_memories.get(current_chat_id, []))
                    except Exception:
                        pass
                    break
                if cmd == 'list-sessions' or cmd == 'list':
                    sess = list_sessions()
                    if not sess:
                        print('No sessions found.')
                    else:
                        print('Saved sessions:')
                for s in sess:
                    print(' -', s)
                    continue
                if cmd in ('use', 'load') and len(parts) >= 2:
                    new_id = parts[1]
                    new_id = re.sub(r'[^A-Za-z0-9_.-]', '_', new_id)[:64]
                    current_chat_id = new_id
                    load_chat_memory(current_chat_id)
                    print(f'Loaded session: {current_chat_id}')
                    continue
                if cmd == 'show':
                    if len(parts) >= 2:
                        target = re.sub(r'[^A-Za-z0-9_.-]', '_', parts[1])[:64]
                        path = memory_file_for(target)
                        if path.exists():
                            try:
                                with open(path, 'r', encoding='utf-8') as f:
                                    data = f.read()
                                    print(data[:4000])
                            except Exception as e:
                                print('Failed to read session file:', e)
                        else:
                            print('Session file not found:', path)
                    else:
                        print('Current session:', current_chat_id)
                    continue
                if cmd == 'provider' and len(parts) >= 2:
                    try:
                        new_provider = LLMProvider(parts[1].lower())
                        llm_client.config.provider = new_provider
                        llm_client.client = llm_client._create_client()
                        print(f"Switched to {new_provider.value.upper()} provider")
                    except ValueError:
                        print(f"Invalid provider: {parts[1]}")
                        print("Valid providers: anthropic, openai, bedrock, gemini")
                    except Exception as e:
                        print(f"Failed to switch provider: {e}")
                    continue
                if cmd == 'chart':
                    # Explicitly trigger chart generation from last tool output
                    print("Chart generation is only available when explicitly requested in queries.")
                    print("Try asking: 'Create a chart showing resource capacity' or 'Generate a chart from the last data'")
                    continue
                print('Unknown command:', cmd)
                continue

            # Run the main routine using the selected session id
            try:
                asyncio.run(run(query, chat_id=current_chat_id))
            except KeyboardInterrupt:
                print('\nInterrupted by user during run; saving session and returning to REPL.')
                try:
                    set_chat_memory(current_chat_id, chat_memories.get(current_chat_id, []))
                except Exception:
                    pass
                continue

    except KeyboardInterrupt:
        print('\nInterrupted. Goodbye.')
        try:
            set_chat_memory(current_chat_id, chat_memories.get(current_chat_id, []))
        except Exception:
            pass
