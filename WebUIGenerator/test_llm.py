#!/usr/bin/env python3
"""
Test Claude connectivity via LiteLLM proxy.
Run: python test_llm.py
"""

import json
import os
import ssl
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

LITELLM_API_BASE = os.environ.get("LITELLM_API_BASE", "")
LITELLM_API_KEY  = os.environ.get("LITELLM_API_KEY", "")
LITELLM_SSL_CERT = os.environ.get("LITELLM_SSL_CERT", "")
MODEL_ID         = os.environ.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6")

print(f"\n{'='*60}")
print("  TurboUIGen — Claude (LiteLLM Proxy) Connectivity Test")
print(f"{'='*60}\n")
print(f"  Proxy   : {LITELLM_API_BASE}")
print(f"  Model   : {MODEL_ID}")
print()

# 1. Check openai package
print("[1] Checking openai package...", end=" ")
try:
    import openai
    print("OK")
except ImportError:
    print("FAILED\n  -> Run: pip install openai")
    sys.exit(1)

# 2. Check httpx
print("[2] Checking httpx package...", end=" ")
try:
    import httpx
    print("OK")
except ImportError:
    print("FAILED\n  -> Run: pip install httpx")
    sys.exit(1)

# 3. Check config
print("[3] Checking LiteLLM configuration...", end=" ")
if not LITELLM_API_BASE:
    print("FAILED\n  -> LITELLM_API_BASE not set in .env")
    sys.exit(1)
if not LITELLM_API_KEY:
    print("FAILED\n  -> LITELLM_API_KEY not set in .env")
    sys.exit(1)
print("OK")

# 4. Build client
print("[4] Creating LiteLLM client...", end=" ")
try:
    import tempfile
    ssl_ctx = ssl.create_default_context()
    if LITELLM_SSL_CERT:
        cert_content = LITELLM_SSL_CERT.replace("\\n", "\n")
        ssl_ctx.load_verify_locations(cadata=cert_content)

    http_client = httpx.Client(verify=ssl_ctx, timeout=httpx.Timeout(120))
    base_url = LITELLM_API_BASE.rstrip("/") + "/v1"
    client = openai.OpenAI(
        base_url=base_url,
        api_key=LITELLM_API_KEY,
        http_client=http_client,
    )
    print("OK")
except Exception as e:
    print(f"FAILED\n  -> {e}")
    sys.exit(1)

# 5. Send a simple test message
print("[5] Sending test message to Claude...", end=" ", flush=True)
try:
    t0 = time.time()
    response = client.chat.completions.create(
        model=MODEL_ID,
        max_tokens=64,
        messages=[{"role": "user", "content": "Say hello in one word."}],
    )
    reply = response.choices[0].message.content or ""
    elapsed = time.time() - t0
    print(f"OK ({elapsed:.1f}s)")
    print(f"\n  Claude said: \"{reply.strip()}\"\n")
except Exception as e:
    print(f"FAILED\n  -> {type(e).__name__}: {e}")
    sys.exit(1)

# 6. Test JSON mode
print("[6] Testing JSON response...", end=" ", flush=True)
try:
    response = client.chat.completions.create(
        model=MODEL_ID,
        max_tokens=128,
        messages=[
            {"role": "system", "content": "Respond with ONLY valid JSON. No markdown, no explanation."},
            {"role": "user", "content": 'Return {"status": "ok", "model": "claude"}'},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    parsed = json.loads(text)
    print(f"OK -> {parsed}")
except Exception as e:
    print(f"FAILED\n  -> {type(e).__name__}: {e}")
    sys.exit(1)

print(f"\n{'='*60}")
print("  All tests passed! Claude via LiteLLM is ready to use.")
print(f"{'='*60}\n")
