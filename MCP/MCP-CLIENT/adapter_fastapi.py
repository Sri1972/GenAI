"""FastAPI adapter that exposes POST /generate-chart
It runs generate_chart_cli.py with the provided query and returns the newest HTML file
from html-charts/ as the HTTP response.

Security: binds to 127.0.0.1 by default when you run uvicorn; do not expose publicly.
"""
import os
import glob
import subprocess
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import HTMLResponse

app = FastAPI()
BASE_DIR = os.path.dirname(__file__)
CHARTS_DIR = os.path.join(BASE_DIR, "html-charts")
CLI_PY = os.path.join(BASE_DIR, "generate_chart_cli.py")

class ChartRequest(BaseModel):
    query: str


def latest_html_file():
    files = glob.glob(os.path.join(CHARTS_DIR, "*.html"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


@app.post("/generate-chart", response_class=HTMLResponse)
async def generate_chart(req: ChartRequest):
    if not req.query or not isinstance(req.query, str):
        raise HTTPException(status_code=400, detail="query is required")
    if not os.path.exists(CLI_PY):
        raise HTTPException(status_code=500, detail=f"CLI helper missing: {CLI_PY}")

    # Run the CLI synchronously and wait
    try:
        # Use same interpreter - on Windows ensure the environment is correct when launching uvicorn
        proc = subprocess.run(["python", CLI_PY, req.query], capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Chart generation timed out")

    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Chart generation failed: {proc.stderr[:1000]}")

    # Give the script a small moment to flush file writes
    time.sleep(0.2)
    path = latest_html_file()
    if not path:
        raise HTTPException(status_code=500, detail="No chart produced")
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html, status_code=200)
