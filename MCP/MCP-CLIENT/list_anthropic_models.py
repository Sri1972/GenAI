#!/usr/bin/env python3
"""
List Anthropic models accessible by the API key in your .env.
Usage:
  python list_anthropic_models.py

Requires: requests (fallback) and/or anthropic SDK. The script reads ANTHROPIC_API_KEY from .env.
"""
import os
import json
from dotenv import load_dotenv

load_dotenv('.env')
API_KEY = os.getenv('ANTHROPIC_API_KEY')

if not API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not found in environment or .env")
    raise SystemExit(1)

# Try the Anthropic SDK first (if installed), otherwise fall back to a direct HTTP request.
try:
    import anthropic
    client = anthropic.Anthropic(api_key=API_KEY)
    try:
        models = client.models.list()
        # models may be a dict-like or object; dump for inspection
        print(json.dumps(models, indent=2, default=str))
        # Try to extract common structure
        mlist = None
        if isinstance(models, dict):
            mlist = models.get('models') or models.get('data') or models
        else:
            # some SDKs return objects with .data or similar
            try:
                mlist = models.models
            except Exception:
                mlist = models
        if isinstance(mlist, (list, tuple)):
            print("\nAvailable models:\n")
            for m in mlist:
                mid = m.get('id') if isinstance(m, dict) else getattr(m, 'id', None)
                desc = m.get('description') if isinstance(m, dict) else getattr(m, 'description', None)
                print(f"- {mid}: {desc}")
        raise SystemExit(0)
    except Exception as e:
        print("Anthropic SDK call failed:", e)
        # fall through to HTTP fallback
except Exception:
    # SDK not available or failed to import, continue to HTTP fallback
    pass

# HTTP fallback
import requests
print("Falling back to direct HTTP call to https://api.anthropic.com/v1/models")
headers = {
    'x-api-key': API_KEY,
    # Use a recent anthropic-version header; adjust if needed per Anthropic docs
    'anthropic-version': '2024-10-03'
}
resp = requests.get('https://api.anthropic.com/v1/models', headers=headers)
try:
    resp.raise_for_status()
except Exception:
    print('Request failed:', resp.status_code, resp.text)
    raise

data = resp.json()
print(json.dumps(data, indent=2, ensure_ascii=False))
# Print a concise list if possible
mlist = data.get('models') or data.get('data') or data
if isinstance(mlist, (list, tuple)):
    print('\nAvailable models:\n')
    for m in mlist:
        mid = m.get('id') if isinstance(m, dict) else None
        desc = m.get('description') if isinstance(m, dict) else None
        print(f"- {mid}: {desc}")
