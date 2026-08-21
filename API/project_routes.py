"""
Project workspace endpoints (Phase A).

A *project* is the unified, persistent workspace that spans every interface (roundtable,
web-app builder, …). These routes are the CRUD + file-upload surface for it. Mounted on the
main app via `app.include_router(project_router)`.

Kept separate from the legacy flat-store project endpoints in server.py (which own
`/api/projects*` and operate on generated/web-apps/*). To avoid colliding with those during
the transition, the new Project store lives under `/api/workspaces`. The UI still calls these
"Projects" — the path is just transport.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents import projects as store

project_router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

# Per reference file. Datasets (CSV/Parquet) can be large; override with TURBOUI_MAX_UPLOAD_MB.
_MAX_UPLOAD_MB = int(os.environ.get("TURBOUI_MAX_UPLOAD_MB", "150"))
_MAX_UPLOAD = _MAX_UPLOAD_MB * 1024 * 1024


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class RenameWebappRequest(BaseModel):
    new_name: str


def _webapp_payload(slug: str, app_id: str) -> dict:
    return {"appId": app_id, "key": store.make_key(slug, app_id), "previewUrl": f"/app/{store.make_key(slug, app_id)}/"}


@project_router.get("")
def list_projects():
    return JSONResponse(store.list_projects())


@project_router.post("")
def create_project(req: CreateProjectRequest):
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name is required.")
    try:
        return JSONResponse(store.create_project(name, req.description), status_code=201)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@project_router.get("/{slug}")
def get_project(slug: str):
    proj = store.get_project(slug)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")
    return JSONResponse(proj)


class ModeRequest(BaseModel):
    mode: str


@project_router.post("/{slug}/default-mode")
def set_default_mode(slug: str, req: ModeRequest):
    try:
        proj = store.set_default_mode(slug, req.mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")
    return JSONResponse(proj)


@project_router.delete("/{slug}")
def delete_project(slug: str):
    if not store.delete_project(slug):
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")
    return JSONResponse({"status": "deleted", "slug": store.slugify(slug)})


@project_router.get("/{slug}/inputs")
def list_inputs(slug: str):
    if not store.exists(slug):
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")
    return JSONResponse(store.list_inputs(slug))


@project_router.post("/{slug}/inputs")
async def upload_input(slug: str, file: UploadFile = File(...)):
    if not store.exists(slug):
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")
    data = await file.read()
    if len(data) > _MAX_UPLOAD:
        raise HTTPException(status_code=413, detail=f"File exceeds the {_MAX_UPLOAD_MB} MB limit.")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    try:
        entry = store.save_input_file(slug, file.filename or "file", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(entry, status_code=201)


@project_router.delete("/{slug}/inputs/{filename}")
def delete_input(slug: str, filename: str):
    if not store.delete_input(slug, filename):
        raise HTTPException(status_code=404, detail="File not found.")
    return JSONResponse({"status": "deleted", "name": filename})


# ── webapp prototypes (project-scoped, keyed <project>--<app-id>) ───────────────

@project_router.get("/{slug}/webapps")
def list_webapps(slug: str):
    if not store.exists(slug):
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")
    return JSONResponse([_webapp_payload(store.slugify(slug), a) for a in store.list_webapps(slug)])


@project_router.post("/{slug}/webapps")
def create_webapp(slug: str):
    if not store.exists(slug):
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")
    app_id = store.create_webapp(slug)
    return JSONResponse(_webapp_payload(store.slugify(slug), app_id), status_code=201)


@project_router.post("/{slug}/webapps/{app_id}/rename")
def rename_webapp(slug: str, app_id: str, req: RenameWebappRequest):
    if not (req.new_name or "").strip():
        raise HTTPException(status_code=400, detail="New name is required.")
    try:
        new_id = store.rename_webapp(slug, app_id, req.new_name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return JSONResponse(_webapp_payload(store.slugify(slug), new_id))


@project_router.delete("/{slug}/webapps/{app_id}")
def delete_webapp(slug: str, app_id: str):
    if not store.delete_webapp(slug, app_id):
        raise HTTPException(status_code=404, detail="Prototype not found.")
    return JSONResponse({"status": "deleted", "appId": app_id})
