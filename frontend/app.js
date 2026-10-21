(() => {
  "use strict";

  const PALETTE = [
    "#f2c94c", "#6fbf73", "#4ea8de", "#f28b82", "#c58af9",
    "#ffb74d", "#81c784", "#64b5f6", "#e57373", "#ba68c8",
    "#ffd54f", "#aed581", "#4dd0e1", "#ff8a65", "#9575cd",
    "#fff176", "#a5d6a7",
  ];

  const state = {
    sets: [],
    current: null,
    selectedPieceId: null,
    canvas: { rows: 5, cols: 5, cells: new Set() },
    solving: false,
  };

  const $ = (id) => document.getElementById(id);

  function cellKey(r, c) {
    return `${r},${c}`;
  }

  function parseKey(k) {
    const [r, c] = k.split(",").map(Number);
    return [r, c];
  }

  function normalizeCells(cells) {
    if (!cells.length) return [];
    const mr = Math.min(...cells.map(([r]) => r));
    const mc = Math.min(...cells.map(([, c]) => c));
    return cells
      .map(([r, c]) => [r - mr, c - mc])
      .sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
  }

  function canvasCells() {
    return normalizeCells([...state.canvas.cells].map(parseKey));
  }

  function loadCellsToCanvas(cells) {
    state.canvas.cells = new Set();
    for (const [r, c] of cells) {
      if (r < state.canvas.rows && c < state.canvas.cols) {
        state.canvas.cells.add(cellKey(r, c));
      }
    }
    renderCanvas();
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail || JSON.stringify(body);
      } catch (_) {
        /* ignore */
      }
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    if (res.status === 204) return null;
    return res.json();
  }

  function syncBoardInputsFromCurrent() {
    if (!state.current) return;
    $("boardRows").value = state.current.board.rows;
    $("boardCols").value = state.current.board.cols;
    $("wrapCols").checked = !!state.current.board.wrap_cols;
    $("uprightOnly").checked = state.current.board.upright_only !== false;
    $("allowMirror").checked = !!state.current.board.allow_mirror;
    $("editorRows").value = state.current.editor?.rows ?? 5;
    $("editorCols").value = state.current.editor?.cols ?? 5;
    state.canvas.rows = Number($("editorRows").value);
    state.canvas.cols = Number($("editorCols").value);
  }

  function readBoardFromInputs() {
    return {
      rows: Number($("boardRows").value) || 7,
      cols: Number($("boardCols").value) || 14,
      wrap_cols: $("wrapCols").checked,
      upright_only: $("uprightOnly").checked,
      allow_mirror: $("allowMirror").checked,
    };
  }

  function snapshot() {
    if (!state.current) return null;
    return {
      id: state.current.id,
      name: state.current.name,
      board: readBoardFromInputs(),
      editor: {
        rows: state.canvas.rows,
        cols: state.canvas.cols,
      },
      pieces: state.current.pieces.map((p) => ({
        id: p.id,
        cells: p.cells.map(([r, c]) => [r, c]),
      })),
    };
  }

  function updateKernelCheck() {
    const board = readBoardFromInputs();
    const target = board.rows * board.cols;
    const total = (state.current?.pieces || []).reduce(
      (sum, p) => sum + (p.cells?.length || 0),
      0,
    );
    const el = $("kernelCheck");
    el.textContent = `核仁合计 ${total} / 目标 ${board.rows}×${board.cols}=${target}`;
    el.classList.toggle("ok", total === target);
    el.classList.toggle("bad", total !== target);
  }

  function renderSetSelect() {
    const sel = $("setSelect");
    sel.innerHTML = "";
    for (const s of state.sets) {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = `${s.name} (${s.piece_count} 件)`;
      sel.appendChild(opt);
    }
    if (state.current) sel.value = state.current.id;
  }

  function renderCanvas() {
    const grid = $("canvasGrid");
    grid.style.gridTemplateColumns = `repeat(${state.canvas.cols}, 2rem)`;
    grid.innerHTML = "";
    for (let r = 0; r < state.canvas.rows; r++) {
      for (let c = 0; c < state.canvas.cols; c++) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "cell" + (state.canvas.cells.has(cellKey(r, c)) ? " on" : "");
        btn.setAttribute("aria-label", `格子 ${r},${c}`);
        btn.addEventListener("click", () => {
          const k = cellKey(r, c);
          if (state.canvas.cells.has(k)) state.canvas.cells.delete(k);
          else state.canvas.cells.add(k);
          renderCanvas();
        });
        grid.appendChild(btn);
      }
    }
  }

  function thumbHtml(cells) {
    const norm = normalizeCells(cells.map(([r, c]) => [r, c]));
    if (!norm.length) {
      return '<div class="piece-thumb" style="grid-template-columns:repeat(1,10px)"><span></span></div>';
    }
    const maxR = Math.max(...norm.map(([r]) => r));
    const maxC = Math.max(...norm.map(([, c]) => c));
    const set = new Set(norm.map(([r, c]) => cellKey(r, c)));
    let html = `<div class="piece-thumb" style="grid-template-columns:repeat(${maxC + 1},10px)">`;
    for (let r = 0; r <= maxR; r++) {
      for (let c = 0; c <= maxC; c++) {
        html += `<span class="${set.has(cellKey(r, c)) ? "filled" : ""}"></span>`;
      }
    }
    html += "</div>";
    return html;
  }

  function renderPieces() {
    const list = $("pieceList");
    list.innerHTML = "";
    if (!state.current) return;
    state.current.pieces.forEach((p, idx) => {
      const li = document.createElement("li");
      li.className = "piece-item" + (p.id === state.selectedPieceId ? " selected" : "");
      li.innerHTML = `${thumbHtml(p.cells)}
        <div class="piece-meta">
          <strong>${p.id}</strong>
          <span>${p.cells.length} 核仁 · #${idx + 1}</span>
        </div>`;
      li.addEventListener("click", () => {
        state.selectedPieceId = p.id;
        const needR = Math.max(0, ...p.cells.map(([r]) => r)) + 1;
        const needC = Math.max(0, ...p.cells.map(([, c]) => c)) + 1;
        if (needR > state.canvas.rows || needC > state.canvas.cols) {
          state.canvas.rows = Math.max(state.canvas.rows, needR);
          state.canvas.cols = Math.max(state.canvas.cols, needC);
          $("editorRows").value = state.canvas.rows;
          $("editorCols").value = state.canvas.cols;
        }
        loadCellsToCanvas(p.cells);
        renderPieces();
      });
      list.appendChild(li);
    });
    updateKernelCheck();
  }

  function colorForLabel(label) {
    const n = parseInt(label, 10);
    if (Number.isFinite(n) && n > 0) return PALETTE[(n - 1) % PALETTE.length];
    let h = 0;
    for (const ch of String(label)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    return PALETTE[h % PALETTE.length];
  }

  function fillBoard(boardEl, board) {
    const rows = board.length;
    const cols = board[0]?.length || 0;
    boardEl.style.gridTemplateColumns = `repeat(${cols}, 1.55rem)`;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const label = board[r][c];
        const cell = document.createElement("div");
        cell.className = "result-cell";
        cell.textContent = label;
        cell.style.background = colorForLabel(label);
        cell.title = `(${r},${c}) = ${label}`;
        boardEl.appendChild(cell);
      }
    }
  }

  function renderResult(result) {
    const status = $("statusBox");
    const host = $("resultBoards");
    const diag = $("diagnostics");
    host.innerHTML = "";
    diag.innerHTML = "";

    if (!result) {
      status.textContent = "";
      return;
    }

    const solutions = result.solutions?.length
      ? result.solutions
      : result.board
        ? [result.board]
        : [];
    const t = result.time_s != null ? ` · ${result.time_s.toFixed(3)}s` : "";
    let summary = `状态：${result.status}${t}`;
    if (solutions.length) {
      summary += ` · ${solutions.length} 个解`;
      if (result.solutions_complete === false) summary += "（可能还有更多）";
    }
    status.textContent = summary;

    for (const msg of result.diagnostics || []) {
      const li = document.createElement("li");
      li.textContent = msg;
      diag.appendChild(li);
    }

    solutions.forEach((board, i) => {
      const block = document.createElement("div");
      if (solutions.length > 1) {
        const label = document.createElement("p");
        label.className = "solution-label";
        label.textContent = `解 ${i + 1}`;
        block.appendChild(label);
      }
      const boardEl = document.createElement("div");
      boardEl.className = "result-board";
      fillBoard(boardEl, board);
      block.appendChild(boardEl);
      host.appendChild(block);
    });
  }

  function nextPieceId() {
    const used = new Set((state.current?.pieces || []).map((p) => p.id));
    let i = 1;
    while (used.has(`P${String(i).padStart(2, "0")}`)) i += 1;
    return `P${String(i).padStart(2, "0")}`;
  }

  async function refreshSets(preferId) {
    state.sets = await api("/api/sets");
    renderSetSelect();
    const id = preferId || state.current?.id || state.sets[0]?.id;
    if (id) await loadSet(id);
  }

  async function loadSet(id) {
    const data = await api(`/api/sets/${encodeURIComponent(id)}`);
    state.current = data;
    state.selectedPieceId = data.pieces[0]?.id || null;
    syncBoardInputsFromCurrent();
    state.canvas.cells = new Set();
    if (state.selectedPieceId) {
      const p = data.pieces.find((x) => x.id === state.selectedPieceId);
      if (p) loadCellsToCanvas(p.cells);
      else renderCanvas();
    } else {
      renderCanvas();
    }
    renderSetSelect();
    renderPieces();
    renderResult(null);
  }

  async function saveCurrent() {
    const snap = snapshot();
    if (!snap) return;
    state.current = await api(`/api/sets/${encodeURIComponent(snap.id)}`, {
      method: "PUT",
      body: JSON.stringify({
        name: snap.name,
        board: snap.board,
        editor: snap.editor,
        pieces: snap.pieces,
      }),
    });
    await refreshSets(state.current.id);
    $("statusBox").textContent = "已保存";
  }

  function bindEvents() {
    $("setSelect").addEventListener("change", async (e) => {
      await loadSet(e.target.value);
    });

    $("btnNewSet").addEventListener("click", async () => {
      const name = prompt("新组名称", "未命名组");
      if (!name) return;
      const created = await api("/api/sets", {
        method: "POST",
        body: JSON.stringify({
          name,
          board: { rows: 7, cols: 14, wrap_cols: true, upright_only: true, allow_mirror: false },
          editor: { rows: 5, cols: 5 },
          pieces: [],
        }),
      });
      await refreshSets(created.id);
    });

    $("btnRenameSet").addEventListener("click", async () => {
      if (!state.current) return;
      const name = prompt("重命名", state.current.name);
      if (!name || name === state.current.name) return;
      state.current.name = name;
      await saveCurrent();
    });

    $("btnDeleteSet").addEventListener("click", async () => {
      if (!state.current) return;
      if (!confirm(`删除组「${state.current.name}」？`)) return;
      await api(`/api/sets/${encodeURIComponent(state.current.id)}`, { method: "DELETE" });
      state.current = null;
      await refreshSets();
    });

    $("btnSaveSet").addEventListener("click", () => saveCurrent().catch(showError));

    $("btnResizeEditor").addEventListener("click", () => {
      const rows = Math.max(1, Math.min(32, Number($("editorRows").value) || 5));
      const cols = Math.max(1, Math.min(32, Number($("editorCols").value) || 5));
      state.canvas.rows = rows;
      state.canvas.cols = cols;
      $("editorRows").value = rows;
      $("editorCols").value = cols;
      const next = new Set();
      for (const k of state.canvas.cells) {
        const [r, c] = parseKey(k);
        if (r < rows && c < cols) next.add(k);
      }
      state.canvas.cells = next;
      renderCanvas();
    });

    $("btnClearCanvas").addEventListener("click", () => {
      state.canvas.cells = new Set();
      renderCanvas();
    });

    $("btnAddPiece").addEventListener("click", () => {
      if (!state.current) return;
      const cells = canvasCells();
      if (!cells.length) {
        alert("画布为空，请先点亮格子");
        return;
      }
      const id = nextPieceId();
      state.current.pieces.push({ id, cells });
      state.selectedPieceId = id;
      state.canvas.cells = new Set();
      renderCanvas();
      renderPieces();
    });

    $("btnOverwritePiece").addEventListener("click", () => {
      if (!state.current || !state.selectedPieceId) {
        alert("请先选中零件");
        return;
      }
      const cells = canvasCells();
      if (!cells.length) {
        alert("画布为空，请先点亮格子");
        return;
      }
      const p = state.current.pieces.find((x) => x.id === state.selectedPieceId);
      if (p) p.cells = cells;
      state.canvas.cells = new Set();
      renderCanvas();
      renderPieces();
    });

    $("btnDeletePiece").addEventListener("click", () => {
      if (!state.current || !state.selectedPieceId) return;
      state.current.pieces = state.current.pieces.filter((p) => p.id !== state.selectedPieceId);
      state.selectedPieceId = state.current.pieces[0]?.id || null;
      if (state.selectedPieceId) {
        const p = state.current.pieces.find((x) => x.id === state.selectedPieceId);
        loadCellsToCanvas(p.cells);
      } else {
        state.canvas.cells = new Set();
        renderCanvas();
      }
      renderPieces();
    });

    $("btnMoveUp").addEventListener("click", () => moveSelected(-1));
    $("btnMoveDown").addEventListener("click", () => moveSelected(1));

    ["boardRows", "boardCols", "wrapCols", "uprightOnly", "allowMirror"].forEach((id) => {
      $(id).addEventListener("input", updateKernelCheck);
      $(id).addEventListener("change", updateKernelCheck);
    });

    $("btnSolve").addEventListener("click", async () => {
      const snap = snapshot();
      if (!snap) return;
      if (state.solving) return;
      state.solving = true;
      $("btnSolve").disabled = true;
      $("statusBox").textContent = "求解中…";
      try {
        const result = await api("/api/solve", {
          method: "POST",
          body: JSON.stringify(snap),
        });
        renderResult(result);
      } catch (err) {
        showError(err);
      } finally {
        state.solving = false;
        $("btnSolve").disabled = false;
      }
    });

    $("btnExport").addEventListener("click", () => {
      const snap = snapshot();
      if (!snap) return;
      const blob = new Blob([JSON.stringify(snap, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${snap.id || "puzzle-set"}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
    });

    $("importFile").addEventListener("change", async (e) => {
      const file = e.target.files?.[0];
      e.target.value = "";
      if (!file) return;
      try {
        const text = await file.text();
        const data = JSON.parse(text);
        const created = await api("/api/sets", {
          method: "POST",
          body: JSON.stringify({
            name: data.name || file.name.replace(/\.json$/i, ""),
            board: data.board || {
              rows: 7,
              cols: 14,
              wrap_cols: true,
              upright_only: true,
              allow_mirror: false,
            },
            editor: data.editor || { rows: 5, cols: 5 },
            pieces: data.pieces || [],
          }),
        });
        await refreshSets(created.id);
        $("statusBox").textContent = "已导入并新建组";
      } catch (err) {
        showError(err);
      }
    });
  }

  function moveSelected(delta) {
    if (!state.current || !state.selectedPieceId) return;
    const arr = state.current.pieces;
    const i = arr.findIndex((p) => p.id === state.selectedPieceId);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= arr.length) return;
    [arr[i], arr[j]] = [arr[j], arr[i]];
    renderPieces();
  }

  function showError(err) {
    console.error(err);
    $("statusBox").textContent = `错误：${err.message || err}`;
  }

  async function init() {
    bindEvents();
    renderCanvas();
    try {
      await refreshSets();
    } catch (err) {
      showError(err);
    }
  }

  init();
})();
