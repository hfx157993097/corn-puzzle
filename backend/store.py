"""JSON file persistence for puzzle sets."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from backend.models import PuzzleSet, PuzzleSetCreate, PuzzleSetSummary, PuzzleSetUpdate
from backend.solver import normalize

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sets"

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _path_for(set_id: str) -> Path:
    if not _SAFE_ID.match(set_id):
        raise ValueError(f"非法组 id: {set_id}")
    return ensure_data_dir() / f"{set_id}.json"


def _normalize_pieces(pieces: list) -> list[dict]:
    out = []
    for p in pieces:
        if hasattr(p, "model_dump"):
            data = p.model_dump()
        else:
            data = dict(p)
        cells = [(int(r), int(c)) for r, c in data.get("cells", [])]
        data["cells"] = [list(cell) for cell in normalize(cells)] if cells else []
        out.append(data)
    return out


def list_sets() -> list[PuzzleSetSummary]:
    ensure_data_dir()
    summaries: list[PuzzleSetSummary] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            summaries.append(
                PuzzleSetSummary(
                    id=data["id"],
                    name=data.get("name", path.stem),
                    piece_count=len(data.get("pieces", [])),
                    board=data.get("board", {"rows": 7, "cols": 14, "wrap_cols": True}),
                )
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return summaries


def get_set(set_id: str) -> PuzzleSet | None:
    path = _path_for(set_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return PuzzleSet.model_validate(data)


def create_set(payload: PuzzleSetCreate, set_id: str | None = None) -> PuzzleSet:
    sid = set_id or str(uuid.uuid4())
    if get_set(sid) is not None:
        raise FileExistsError(f"组已存在: {sid}")
    puzzle = PuzzleSet(
        id=sid,
        name=payload.name,
        board=payload.board,
        editor=payload.editor,
        pieces=_normalize_pieces(payload.pieces),  # type: ignore[arg-type]
    )
    path = _path_for(sid)
    path.write_text(
        json.dumps(puzzle.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return puzzle


def update_set(set_id: str, payload: PuzzleSetUpdate) -> PuzzleSet | None:
    existing = get_set(set_id)
    if existing is None:
        return None
    data = existing.model_dump()
    patch = payload.model_dump(exclude_unset=True)
    if "pieces" in patch and patch["pieces"] is not None:
        patch["pieces"] = _normalize_pieces(patch["pieces"])
    data.update(patch)
    data["id"] = set_id
    puzzle = PuzzleSet.model_validate(data)
    path = _path_for(set_id)
    path.write_text(
        json.dumps(puzzle.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return puzzle


def delete_set(set_id: str) -> bool:
    path = _path_for(set_id)
    if not path.is_file():
        return False
    path.unlink()
    return True
