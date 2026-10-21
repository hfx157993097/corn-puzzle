"""Solver tests: 17-piece default corn set must be feasible."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_ROOT))

from backend.solver import diagnose, get_orientations, normalize, placements_for, solve  # noqa: E402

PIECES = {
    "P01": [(0, 2), (0, 3), (1, 2), (2, 0), (2, 1), (2, 2)],
    "P02": [(0, 0), (0, 1), (1, 0), (1, 1), (1, 2)],
    "P03": [(0, 2), (1, 0), (1, 1), (1, 2)],
    "P04": [(0, 1), (0, 2), (1, 0), (1, 1), (1, 2)],
    "P05": [(0, 0), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)],
    "P06": [
        (0, 0),
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
    ],
    "P07": [(0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)],
    "P08": [(0, 0), (0, 1), (1, 0), (1, 1), (1, 2), (2, 0)],
    "P09": [(0, 0), (0, 1), (0, 2), (1, 1), (2, 1)],
    "P10": [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 0)],
    "P11": [(0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)],
    "P12": [(0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)],
    "P13": [(0, 0), (0, 1), (0, 2), (0, 3)],
    "P14": [(0, 2), (1, 2), (2, 1), (2, 2), (3, 0), (3, 1), (3, 2)],
    "P15": [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0)],
    "P16": [(0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2)],
    "P17": [(0, 0), (0, 1), (1, 0), (1, 1), (1, 2)],
}


def test_kernel_count():
    assert sum(len(v) for v in PIECES.values()) == 7 * 14


def test_normalize():
    assert normalize([(2, 3), (2, 4)]) == ((0, 0), (0, 1))


def test_orientation_flags_are_independent():
    # 手性 L 四连：正放/倒置 2 种；再加镜像 4 种；四向旋转 4 种；旋转加镜像 8 种。
    shape = [(0, 0), (1, 0), (2, 0), (2, 1)]
    upright = get_orientations(shape, upright_only=True, allow_mirror=False)
    upright_mirror = get_orientations(shape, upright_only=True, allow_mirror=True)
    turns = get_orientations(shape, upright_only=False, allow_mirror=False)
    free = get_orientations(shape, upright_only=False, allow_mirror=True)
    assert len(upright) == 2
    assert len(upright_mirror) == 4
    assert len(turns) == 4
    assert len(free) == 8
    half = normalize([(-r, -c) for r, c in shape])
    quarter = normalize([(c, -r) for r, c in shape])
    got = {tuple(o) for o in upright}
    assert half in got
    assert quarter not in got
    assert all(tuple(o) in {tuple(x) for x in free} for o in upright)

    vertical = [(0, 0), (1, 0)]
    placed = placements_for(
        vertical, rows=2, cols=2, wrap_cols=False, upright_only=True, allow_mirror=False
    )
    assert set(placed) == {((0, 0), (1, 0)), ((0, 1), (1, 1))}


def _solve_small(pieces, rows, cols, wrap_cols):
    return solve(
        pieces,
        rows=rows,
        cols=cols,
        wrap_cols=wrap_cols,
        upright_only=True,
        allow_mirror=False,
        time_limit_s=5.0,
    )


def test_enumerate_distinct_solutions():
    swapped = _solve_small({"A": [(0, 0)], "B": [(0, 0)]}, rows=1, cols=2, wrap_cols=False)
    assert swapped["status"] in ("OPTIMAL", "FEASIBLE")
    assert len(swapped["solutions"]) == 1
    assert swapped["solutions_complete"] is True

    different = _solve_small(
        {"D": [(0, 0), (0, 1)], "M": [(0, 0)]}, rows=1, cols=3, wrap_cols=False
    )
    assert len(different["solutions"]) == 2
    assert different["solutions_complete"] is True

    shifted = _solve_small(
        {"D": [(0, 0), (0, 1)], "M": [(0, 0)]}, rows=1, cols=3, wrap_cols=True
    )
    assert len(shifted["solutions"]) == 1
    assert shifted["solutions_complete"] is True

    same_and_shifted = _solve_small(
        {"A": [(0, 0), (0, 1)], "B": [(0, 0), (0, 1)]},
        rows=1,
        cols=4,
        wrap_cols=True,
    )
    assert len(same_and_shifted["solutions"]) == 1
    assert same_and_shifted["solutions_complete"] is True


def test_wrap_vs_no_wrap_placements():
    # Domino: wrap allows spanning the left/right edge, e.g. cols 2+0 on a 3-col board.
    shape = [(0, 0), (0, 1)]
    wrap = placements_for(shape, rows=2, cols=3, wrap_cols=True)
    flat = placements_for(shape, rows=2, cols=3, wrap_cols=False)
    assert len(wrap) > len(flat)


def test_diagnose_count_mismatch():
    msgs = diagnose({"A": [(0, 0)]}, rows=2, cols=2, wrap_cols=False)
    assert any("少" in m for m in msgs)


def test_default_json_matches_pieces():
    path = APP_ROOT / "data" / "sets" / "default-corn-7x14.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["board"]["rows"] == 7
    assert data["board"]["cols"] == 14
    assert data["board"]["wrap_cols"] is True
    assert data["board"]["upright_only"] is True
    assert data["board"]["allow_mirror"] is False
    assert len(data["pieces"]) == 17
    assert len({p["id"] for p in data["pieces"]}) == 17
    assert sum(len(p["cells"]) for p in data["pieces"]) == 7 * 14


def test_solve_default_corn_feasible():
    result = solve(
        PIECES,
        rows=7,
        cols=14,
        wrap_cols=True,
        time_limit_s=60.0,
        upright_only=False,
        allow_mirror=True,
    )
    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    assert result["board"] is not None
    assert len(result["board"]) == 7
    assert len(result["board"][0]) == 14
    # every cell filled
    labels = {cell for row in result["board"] for cell in row}
    assert ".." not in labels
    # covering uses each piece once: 98 cells, 17 distinct labels
    assert len(labels) == 17


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
