"""
AskMobility REST API
POST /askMobility  { "product_code": "CFI", "nlq": "...", "session_id": "<optional>" }
"""

import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

load_dotenv()

from agent import run_agent
from product_registry import resolve_mcp_server
from session_manager import load_session, new_session, save_session, session_exists

app = FastAPI(
    title="AskMobility",
    description="LLM-powered automotive data API. Ask questions in plain English.",
    version="1.0.0",
)


class AskRequest(BaseModel):
    product_code: str = Field(
        ...,
        description="Product code identifying the data source (e.g. CFI, CS4)",
        examples=["CFI"],
    )
    nlq: str = Field(
        ...,
        description="Natural language question",
        examples=["What are new registrations for Dodge by region and model?"],
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session ID to continue an existing chat. Omit to start a new session.",
    )


class AskResponse(BaseModel):
    session_id: str
    product_code: str
    nlq: str
    answer: str
    chart_path: str | None = Field(
        default=None,
        description="Absolute path to the generated HTML chart file, if one was produced.",
    )


def log(msg: str):
    print(msg, flush=True, file=sys.stdout)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    log(f"[API] 422 Validation error | body: {body.decode()[:500]} | errors: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.post("/askMobility", response_model=AskResponse)
async def ask(request: AskRequest):
    log(f"\n{'='*60}")
    log(f"[API] POST /askMobility")
    log(f"[API]   product_code : {request.product_code}")
    log(f"[API]   session_id   : {request.session_id or '(new session)'}")
    log(f"[API]   nlq          : {request.nlq}")
    log(f"{'='*60}")

    # Resolve MCP server
    try:
        mcp_server_key = resolve_mcp_server(request.product_code)
        log(f"[API] Resolved MCP server: {mcp_server_key}")
    except ValueError as e:
        log(f"[API] ERROR: Unknown product code — {e}")
        raise HTTPException(status_code=400, detail=str(e))

    # Load or validate session
    history = None
    if request.session_id:
        if not session_exists(request.session_id):
            log(f"[API] ERROR: Session not found: {request.session_id}")
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Session '{request.session_id}' not found. "
                    "It may have been deleted or the ID is incorrect. "
                    "Omit session_id to start a new session."
                ),
            )
        session_data = load_session(request.session_id)
        history = session_data["messages"]
        log(f"[API] Loaded session {request.session_id} — {len(history)} messages in history")
    else:
        log("[API] No session_id — starting fresh")

    # Run agentic loop
    log("[API] Handing off to agent loop ...")
    try:
        answer, chart_path, updated_messages = await run_agent(
            nlq=request.nlq,
            mcp_server_key=mcp_server_key,
            history=history,
        )
    except Exception as e:
        log(f"[API] ERROR in agent: {e}")
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    log(f"[API] Agent done — {len(updated_messages)} total messages")
    if chart_path:
        log(f"[API] Chart generated: {chart_path}")

    # Persist session
    if request.session_id:
        save_session(request.session_id, updated_messages)
        session_id = request.session_id
        log(f"[API] Session updated: {session_id}")
    else:
        session_id = new_session(request.product_code, updated_messages)
        log(f"[API] New session created: {session_id}")

    log(f"[API] Returning response | session_id={session_id}")
    return AskResponse(
        session_id=session_id,
        product_code=request.product_code,
        nlq=request.nlq,
        answer=answer,
        chart_path=chart_path,
    )


@app.get("/products")
def list_products():
    from product_registry import PRODUCT_MCP_MAP
    return {"products": [{"code": k, "mcp_server": v} for k, v in PRODUCT_MCP_MAP.items()]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/answer/{session_id}", response_class=PlainTextResponse)
def get_answer(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    session_data = load_session(session_id)
    answers = [msg["content"] for msg in session_data["messages"] if msg.get("role") == "assistant" and msg.get("content")]
    if not answers:
        raise HTTPException(status_code=404, detail="No answer found in session.")
    return "\n\n---\n\n".join(answers)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("CLIENT_API_PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
