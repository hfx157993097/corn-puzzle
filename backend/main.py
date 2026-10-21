"""FastAPI app: sets CRUD, solve API, static frontend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.models import (
    PuzzleSet,
    PuzzleSetCreate,
    PuzzleSetSummary,
    PuzzleSetUpdate,
    SolveRequest,
    SolveResponse,
)
from backend import store
from backend.solver import solve

APP_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = APP_ROOT / "frontend"

app = FastAPI(title="玉米拼图网页编辑器", version="1.0.0")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "corn-puzzle-editor"}


@app.get("/api/sets", response_model=list[PuzzleSetSummary])
def api_list_sets() -> list[PuzzleSetSummary]:
    return store.list_sets()


@app.post("/api/sets", response_model=PuzzleSet, status_code=201)
def api_create_set(payload: PuzzleSetCreate) -> PuzzleSet:
    try:
        return store.create_set(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/sets/{set_id}", response_model=PuzzleSet)
def api_get_set(set_id: str) -> PuzzleSet:
    try:
        puzzle = store.get_set(set_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if puzzle is None:
        raise HTTPException(status_code=404, detail="组不存在")
    return puzzle


@app.put("/api/sets/{set_id}", response_model=PuzzleSet)
def api_update_set(set_id: str, payload: PuzzleSetUpdate) -> PuzzleSet:
    try:
        puzzle = store.update_set(set_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if puzzle is None:
        raise HTTPException(status_code=404, detail="组不存在")
    return puzzle


@app.delete("/api/sets/{set_id}")
def api_delete_set(set_id: str) -> dict:
    try:
        ok = store.delete_set(set_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="组不存在")
    return {"ok": True, "id": set_id}


@app.post("/api/solve", response_model=SolveResponse)
def api_solve(payload: SolveRequest) -> SolveResponse:
    board = payload.board
    pieces = [{"id": p.id, "cells": p.cells} for p in payload.pieces]
    result = solve(
        pieces,
        rows=board.rows,
        cols=board.cols,
        wrap_cols=board.wrap_cols,
        time_limit_s=payload.time_limit_s,
        upright_only=board.upright_only,
        allow_mirror=board.allow_mirror,
    )
    return SolveResponse(**result)


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
