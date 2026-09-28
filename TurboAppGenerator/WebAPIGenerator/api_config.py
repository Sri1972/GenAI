"""
WebAPIGenerator — central configuration.

Deliberately named api_config.py (not config.py) and paired with the api_agents/
package (not agents/) so this project's modules never collide with WebUIGenerator's
or FigmaMockupGenerator's same-named modules on sys.path — see run.py's comment on
why WebUIGenerator vs FigmaMockupGenerator ordering matters and this project's doesn't.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT.parent / ".env")

TURBOUI_HOST = os.environ.get("TURBOUI_HOST", "localhost")

# Mirrors WebUIGenerator/config.py's generated/ layout exactly: a GENERATED_ROOT
# holding one dir per project type, with registry/ports files at the root (not
# inside the project dir itself) — and, just as importantly, this is what
# .gitignore's existing "generated/*" ignore rules are written to match.
GENERATED_ROOT = ROOT / "generated"
WEB_API_DIR    = GENERATED_ROOT / "web-api"
WEB_API_DIR.mkdir(parents=True, exist_ok=True)

REGISTRY_FILE = GENERATED_ROOT / "projects-web-api.json"
PORTS_FILE    = GENERATED_ROOT / ".ports.json"

# Fresh port range, clear of WebUIGenerator's API_PORT_START=8200 pool (used for
# generated web apps' companion data-API servers).
PORT_START = int(os.environ.get("TURBOUI_WEBAPI_PORT_START", "8400"))


def project_url(port: int) -> str:
    return f"http://{TURBOUI_HOST}:{port}"


def protected_env_file(project_name: str) -> Path:
    """
    A copy of the project's .env kept OUTSIDE its own directory — the generated
    app itself only knows about files under its own project root, so it has no
    way to touch this one. Needed because at least one generated Java app has
    been observed overwriting its own .env at runtime with a fresh "startup
    banner" password and, critically, without preserving API_AUTH_TYPE — meaning
    the NEXT restart reads the now-corrupted file and silently starts with auth
    disabled entirely. The runner and the platform's auth-forwarding endpoints
    should read from here, not from inside the project directory.
    """
    return GENERATED_ROOT / f".env.{project_name}"
