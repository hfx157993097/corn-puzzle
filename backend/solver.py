"""Configurable CP-SAT solver for corn cob / polyomino puzzles."""

from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model


def normalize(
    cells: list[tuple[int, int]] | set[tuple[int, int]] | list[list[int]],
) -> tuple[tuple[int, int], ...]:
    parsed = [(int(r), int(c)) for r, c in cells]
    if not parsed:
        return ()
    mr = min(r for r, _ in parsed)
    mc = min(c for _, c in parsed)
    return tuple(sorted((r - mr, c - mc) for r, c in parsed))


def get_orientations(
    cells: list[tuple[int, int]],
    upright_only: bool = True,
    allow_mirror: bool = False,
) -> list[list[tuple[int, int]]]:
    """Distinct orientations of a piece.

    upright_only: 只保留正放与倒置（0°、180°）。
    allow_mirror: 另外允许左右翻转。两个开关互不影响。
    """
    if not cells:
        return []
    base = frozenset((int(r), int(c)) for r, c in cells)
    seen: set[tuple[tuple[int, int], ...]] = set()
    out: list[list[tuple[int, int]]] = []

    def add_family(start: frozenset[tuple[int, int]]) -> None:
        cur = start
        for quarter in range(4):
            if not upright_only or quarter % 2 == 0:
                normed = normalize(cur)
                if normed not in seen:
                    seen.add(normed)
                    out.append(list(normed))
            cur = frozenset((c, -r) for r, c in cur)

    add_family(base)
    if allow_mirror:
        add_family(frozenset((r, -c) for r, c in base))
    return out


def placements_for(
    shape: list[tuple[int, int]],
    rows: int,
    cols: int,
    wrap_cols: bool = True,
    upright_only: bool = True,
    allow_mirror: bool = False,
) -> list[tuple[tuple[int, int], ...]]:
    """Enumerate every legal placement on the grid."""
    found: set[tuple[tuple[int, int], ...]] = set()
    for ori in get_orientations(shape, upright_only=upright_only, allow_mirror=allow_mirror):
        max_r = max(r for r, _ in ori)
        max_c = max(c for _, c in ori)
        for r0 in range(rows - max_r):
            if wrap_cols:
                c_range = range(cols)
            else:
                c_range = range(cols - max_c)
            for c0 in c_range:
                cells: list[tuple[int, int]] = []
                ok = True
                for dr, dc in ori:
                    rr = r0 + dr
                    if wrap_cols:
                        cc = (c0 + dc) % cols
                    else:
                        cc = c0 + dc
                        if not (0 <= cc < cols):
                            ok = False
                            break
                    if not (0 <= rr < rows):
                        ok = False
                        break
                    cells.append((rr, cc))
                if ok:
                    found.add(tuple(sorted(cells)))
    return list(found)


def _piece_label(name: str, index: int) -> str:
    """Stable short label for board cells (prefer trailing digits)."""
    digits = "".join(ch for ch in name if ch.isdigit())
    if digits:
        return digits.zfill(2)[-2:]
    return f"{index + 1:02d}"


def diagnose(
    pieces: dict[str, list[tuple[int, int]]],
    rows: int,
    cols: int,
    wrap_cols: bool = True,
    placement_counts: dict[str, int] | None = None,
    upright_only: bool = True,
    allow_mirror: bool = False,
) -> list[str]:
    """Human-readable pre-solve diagnostics (always run)."""
    diagnostics: list[str] = []
    target = rows * cols
    total = sum(len(v) for v in pieces.values())
    if total != target:
        diff = total - target
        if diff > 0:
            diagnostics.append(
                f"核仁总数 {total} 比目标格数 {rows}×{cols}={target} 多 {diff} 格，请删减零件核仁。"
            )
        else:
            diagnostics.append(
                f"核仁总数 {total} 比目标格数 {rows}×{cols}={target} 少 {-diff} 格，请补画零件核仁。"
            )

    empty = [name for name, shape in pieces.items() if not shape]
    if empty:
        diagnostics.append(f"空零件（无核仁）：{', '.join(empty)}")

    if placement_counts is not None:
        no_place = [name for name, n in placement_counts.items() if n == 0 and pieces.get(name)]
        if no_place:
            limits: list[str] = []
            if upright_only:
                limits.append("只能正放或倒置，横放不计入")
            if not allow_mirror:
                limits.append("镜像不计入")
            extra = f"（{'；'.join(limits)}）" if limits else ""
            diagnostics.append(
                f"以下零件在当前棋盘上无合法放置（过大或高度超过 {rows} 行）：{', '.join(no_place)}{extra}"
            )

    shape_owners: dict[tuple[tuple[int, int], ...], list[str]] = {}
    for name, shape in pieces.items():
        if not shape:
            continue
        key = normalize(shape)
        shape_owners.setdefault(key, []).append(name)
    for names in shape_owners.values():
        if len(names) > 1:
            diagnostics.append(f"重复全等形状警告（不阻止求解）：{', '.join(names)}")

    return diagnostics


SOLUTION_CAP = 48


def _shape_signature(
    shape: list[tuple[int, int]],
    upright_only: bool,
    allow_mirror: bool,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    oris = get_orientations(shape, upright_only=upright_only, allow_mirror=allow_mirror)
    return tuple(sorted(tuple(ori) for ori in oris))


def _interchangeable_groups(
    piece_map: dict[str, list[tuple[int, int]]],
    upright_only: bool,
    allow_mirror: bool,
) -> list[list[str]]:
    """Pieces that share the same allowed orientations can swap labels."""
    buckets: dict[tuple[tuple[tuple[int, int], ...], ...], list[str]] = {}
    order: list[tuple[tuple[tuple[int, int], ...], ...]] = []
    for name, shape in piece_map.items():
        if not shape:
            continue
        sig = _shape_signature(shape, upright_only, allow_mirror)
        if sig not in buckets:
            order.append(sig)
            buckets[sig] = []
        buckets[sig].append(name)
    return [buckets[sig] for sig in order]


def _column_shifts(
    cells: tuple[tuple[int, int], ...] | list[tuple[int, int]],
    cols: int,
) -> list[tuple[tuple[int, int], ...]]:
    found: list[tuple[tuple[int, int], ...]] = []
    for shift in range(cols):
        found.append(tuple(sorted((r, (c + shift) % cols) for r, c in cells)))
    return found


def _add_identical_order(
    model: cp_model.CpModel,
    by_piece: dict[str, list[tuple[cp_model.IntVar, tuple[tuple[int, int], ...]]]],
    groups: list[list[str]],
) -> None:
    """Force a single labeling when several pieces have the same shape."""
    rank_of: dict[tuple[tuple[int, int], ...], int] = {}
    for vars_for_piece in by_piece.values():
        for _var, cells in vars_for_piece:
            rank_of.setdefault(tuple(sorted(cells)), 0)
    for index, key in enumerate(sorted(rank_of)):
        rank_of[key] = index
    if not rank_of:
        return
    max_rank = max(rank_of.values())
    for names in groups:
        if len(names) < 2:
            continue
        order_vars: list[cp_model.IntVar] = []
        for name in names:
            terms = [
                rank_of[tuple(sorted(cells))] * var for var, cells in by_piece[name]
            ]
            order_var = model.NewIntVar(0, max_rank, f"ord_{name}")
            model.Add(order_var == sum(terms))
            order_vars.append(order_var)
        for left, right in zip(order_vars, order_vars[1:]):
            model.Add(left < right)


def _break_column_shifts(
    model: cp_model.CpModel,
    by_piece: dict[str, list[tuple[cp_model.IntVar, tuple[tuple[int, int], ...]]]],
    groups: list[list[str]],
    cols: int,
    wrap_cols: bool,
) -> None:
    """Keep one horizontal phase of a cylinder by pinning a unique piece."""
    if not wrap_cols or cols <= 1:
        return
    unique = [names[0] for names in groups if len(names) == 1]
    if not unique:
        return
    name = unique[0]
    allowed: list[cp_model.IntVar] = []
    for var, cells in by_piece[name]:
        key = tuple(sorted(cells))
        if key == min(_column_shifts(key, cols)):
            allowed.append(var)
    if allowed:
        model.Add(sum(allowed) == 1)


class _SolutionCollector(cp_model.CpSolverSolutionCallback):
    """Collect boards that differ by more than a label swap or a column shift."""

    def __init__(
        self,
        by_piece: dict[str, list[tuple[Any, tuple[tuple[int, int], ...]]]],
        rows: int,
        cols: int,
        cap: int,
        groups: list[list[str]],
        wrap_cols: bool,
    ) -> None:
        super().__init__()
        self._by_piece = list(by_piece.items())
        self._rows = rows
        self._cols = cols
        self._cap = cap
        self._wrap = wrap_cols
        self._seen: set[tuple] = set()
        self._name_group = {
            name: index for index, names in enumerate(groups) for name in names
        }
        self.boards: list[list[list[str]]] = []
        self.hit_cap = False

    def _canonical_key(
        self, assignment: dict[str, tuple[tuple[int, int], ...]]
    ) -> tuple:
        by_group: dict[int, list[tuple[tuple[int, int], ...]]] = {}
        for name, cells in assignment.items():
            by_group.setdefault(self._name_group[name], []).append(tuple(sorted(cells)))
        cell_label: dict[tuple[int, int], tuple[int, int]] = {}
        for group_index, regions in by_group.items():
            for rank, region in enumerate(sorted(regions)):
                for cell in region:
                    cell_label[cell] = (group_index, rank)

        def view(shift: int) -> tuple:
            return tuple(
                tuple(
                    cell_label[(r, (c + shift) % self._cols if self._wrap else c)]
                    for c in range(self._cols)
                )
                for r in range(self._rows)
            )

        shifts = range(self._cols) if self._wrap else range(1)
        return min(view(shift) for shift in shifts)

    def on_solution_callback(self) -> None:
        if len(self.boards) >= self._cap:
            self.hit_cap = True
            self.StopSearch()
            return
        assignment: dict[str, tuple[tuple[int, int], ...]] = {}
        board = [[".." for _ in range(self._cols)] for _ in range(self._rows)]
        for idx, (name, vars_for_piece) in enumerate(self._by_piece):
            label = _piece_label(name, idx)
            for var, cells in vars_for_piece:
                if self.Value(var):
                    assignment[name] = tuple(cells)
                    for r, c in cells:
                        board[r][c] = label
                    break
        key = self._canonical_key(assignment)
        if key in self._seen:
            return
        self._seen.add(key)
        self.boards.append(board)
        if len(self.boards) >= self._cap:
            self.hit_cap = True
            self.StopSearch()


def _result(
    status: str,
    diagnostics: list[str],
    time_s: float = 0.0,
    boards: list[list[list[str]]] | None = None,
    solutions_complete: bool = True,
) -> dict[str, Any]:
    found = boards or []
    return {
        "status": status,
        "board": found[0] if found else None,
        "solutions": found,
        "solutions_complete": solutions_complete,
        "time_s": time_s,
        "diagnostics": diagnostics,
    }


def solve(
    pieces: dict[str, list[tuple[int, int]]] | list[dict[str, Any]],
    rows: int,
    cols: int,
    wrap_cols: bool = True,
    time_limit_s: float = 60.0,
    upright_only: bool = True,
    allow_mirror: bool = False,
) -> dict[str, Any]:
    """Solve a piece set on a configurable board.

    Returns status, the first board, every board found (capped), time, diagnostics.
    """
    if isinstance(pieces, list):
        piece_map: dict[str, list[tuple[int, int]]] = {}
        for item in pieces:
            pid = str(item["id"])
            cells = [(int(r), int(c)) for r, c in item.get("cells", [])]
            piece_map[pid] = list(normalize(cells)) if cells else []
    else:
        piece_map = {
            name: list(normalize(shape)) if shape else []
            for name, shape in pieces.items()
        }

    placement_counts: dict[str, int] = {}
    placements: dict[str, list[tuple[tuple[int, int], ...]]] = {}
    for name, shape in piece_map.items():
        if not shape:
            placements[name] = []
            placement_counts[name] = 0
            continue
        pls = placements_for(
            shape,
            rows,
            cols,
            wrap_cols,
            upright_only=upright_only,
            allow_mirror=allow_mirror,
        )
        placements[name] = pls
        placement_counts[name] = len(pls)

    diagnostics = diagnose(
        piece_map,
        rows,
        cols,
        wrap_cols,
        placement_counts,
        upright_only=upright_only,
        allow_mirror=allow_mirror,
    )

    if not piece_map:
        return _result("MODEL_INVALID", diagnostics + ["没有零件，无法求解。"])

    if any(len(s) == 0 for s in piece_map.values()):
        return _result("MODEL_INVALID", diagnostics)

    if any(n == 0 for n in placement_counts.values()):
        return _result("INFEASIBLE", diagnostics)

    model = cp_model.CpModel()
    by_piece: dict[str, list[tuple[cp_model.IntVar, tuple[tuple[int, int], ...]]]] = {}
    by_cell: dict[tuple[int, int], list[cp_model.IntVar]] = {
        (r, c): [] for r in range(rows) for c in range(cols)
    }

    for name, pls in placements.items():
        vars_for_piece: list[tuple[cp_model.IntVar, tuple[tuple[int, int], ...]]] = []
        for i, cells in enumerate(pls):
            v = model.NewBoolVar(f"{name}_{i}")
            vars_for_piece.append((v, cells))
            for cell in cells:
                by_cell[cell].append(v)
        by_piece[name] = vars_for_piece
        model.Add(sum(v for v, _ in vars_for_piece) == 1)

    for covering in by_cell.values():
        model.Add(sum(covering) == 1)

    groups = _interchangeable_groups(piece_map, upright_only, allow_mirror)
    _add_identical_order(model, by_piece, groups)
    _break_column_shifts(model, by_piece, groups, cols, wrap_cols)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    solver.parameters.enumerate_all_solutions = True
    collector = _SolutionCollector(
        by_piece, rows, cols, SOLUTION_CAP, groups, wrap_cols
    )
    status = solver.Solve(model, collector)
    status_name = solver.StatusName(status)
    time_s = float(solver.WallTime())
    boards = collector.boards
    complete = status == cp_model.OPTIMAL and not collector.hit_cap
    if boards:
        folded = []
        if any(len(names) > 1 for names in groups):
            folded.append("相同零件对换")
        if wrap_cols:
            folded.append("左右闭环下的左右平移")
        if folded:
            diagnostics = diagnostics + ["、".join(folded) + "视为同一个解，不重复展示。"]

    if collector.hit_cap:
        diagnostics = diagnostics + [
            f"已展示 {len(boards)} 个解，达到上限，后面的解没有继续枚举。"
        ]
    elif status == cp_model.UNKNOWN:
        if boards:
            diagnostics = diagnostics + [
                f"时限内找到 {len(boards)} 个解，搜索未完成，可能还有别的解。"
            ]
        else:
            diagnostics = diagnostics + [
                f"求解超时或未给出结论（时限 {time_limit_s:.0f}s，耗时 {time_s:.3f}s）。"
            ]
        return _result(status_name, diagnostics, time_s, boards, solutions_complete=False)

    if not boards:
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE) and not diagnostics:
            diagnostics = [f"求解失败：{status_name}"]
        return _result(status_name, diagnostics, time_s, solutions_complete=complete)

    return _result(status_name, diagnostics, time_s, boards, solutions_complete=complete)
