from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import FilePayload, RunRequest, RunResponse
from .runtime import execute
from .workspace import Workspace

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Ollaborate Studio", version="0.1.0")
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "product": "Ollaborate Studio"}


@app.get("/api/files")
async def list_files(workspace: str = ".") -> dict[str, list[str]]:
    try:
        return {"files": Workspace(workspace).list_files()}
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/file")
async def read_file(path: str, workspace: str = ".") -> FilePayload:
    try:
        return FilePayload(path=path, content=Workspace(workspace).read_file(path))
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.put("/api/file")
async def write_file(payload: FilePayload, workspace: str = ".") -> dict[str, str]:
    try:
        result = Workspace(workspace).write_file(payload.path, payload.content)
        return {"status": result}
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/runs", response_model=RunResponse)
async def run_team(request: RunRequest) -> RunResponse:
    try:
        return await execute(request)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


def run() -> None:
    uvicorn.run("ollaborate_studio.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()

