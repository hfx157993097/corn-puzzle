"""Pydantic models for the corn puzzle API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BoardConfig(BaseModel):
    rows: int = Field(default=7, ge=1, le=64)
    cols: int = Field(default=14, ge=1, le=64)
    wrap_cols: bool = True
    upright_only: bool = True
    allow_mirror: bool = False


class EditorConfig(BaseModel):
    rows: int = Field(default=5, ge=1, le=32)
    cols: int = Field(default=5, ge=1, le=32)


class Piece(BaseModel):
    id: str
    cells: list[list[int]] = Field(default_factory=list)


class PuzzleSet(BaseModel):
    id: str
    name: str
    board: BoardConfig = Field(default_factory=BoardConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    pieces: list[Piece] = Field(default_factory=list)


class PuzzleSetCreate(BaseModel):
    name: str = "未命名组"
    board: BoardConfig = Field(default_factory=BoardConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    pieces: list[Piece] = Field(default_factory=list)


class PuzzleSetUpdate(BaseModel):
    name: str | None = None
    board: BoardConfig | None = None
    editor: EditorConfig | None = None
    pieces: list[Piece] | None = None


class PuzzleSetSummary(BaseModel):
    id: str
    name: str
    piece_count: int
    board: BoardConfig


class SolveRequest(BaseModel):
    """Snapshot of a set used for solving (need not be persisted)."""

    id: str | None = None
    name: str | None = None
    board: BoardConfig = Field(default_factory=BoardConfig)
    editor: EditorConfig | None = None
    pieces: list[Piece] = Field(default_factory=list)
    time_limit_s: float = Field(default=60.0, ge=1.0, le=600.0)


class SolveResponse(BaseModel):
    status: str
    board: list[list[str]] | None = None
    solutions: list[list[list[str]]] = Field(default_factory=list)
    solutions_complete: bool = True
    time_s: float = 0.0
    diagnostics: list[str] = Field(default_factory=list)
