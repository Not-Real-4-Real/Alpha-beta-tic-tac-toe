import math
import queue
import threading
import time
import tkinter as tk
from functools import partial
from tkinter import ttk

from evaluation.v3 import ThreatTracker, make_weights
from main import (
    DIRS,
    EMPTY,
    OTHER,
    best_move,
    check_win,
    evaluate,
    legal_moves,
)
from move_ordering.v2 import rank_candidates


def find_winning_cells(board, r, c, player, K):
    """Return the list of (row, col) cells forming a winning line of length >= K."""
    R, C = len(board), len(board[0])
    for dr, dc in DIRS:
        line = [(r, c)]
        for sign in (1, -1):
            i, j = r + sign * dr, c + sign * dc
            while 0 <= i < R and 0 <= j < C and board[i][j] == player:
                if sign == 1:
                    line.append((i, j))
                else:
                    line.insert(0, (i, j))
                i += sign * dr
                j += sign * dc
        if len(line) >= K:
            return line
    return []


def get_optimized_candidates(board, max_dist=2):
    """Return empty cells within max_dist Chebyshev distance of any placed stone."""
    R, C = len(board), len(board[0])
    occupied = [(r, c) for r in range(R) for c in range(C) if board[r][c] != EMPTY]
    if not occupied:
        return [(R // 2, C // 2)]

    cand_set = set()
    for r, c in occupied:
        for nr in range(max(0, r - max_dist), min(R, r + max_dist + 1)):
            for nc in range(max(0, c - max_dist), min(C, c + max_dist + 1)):
                if board[nr][nc] == EMPTY:
                    cand_set.add((nr, nc))

    return list(cand_set) if cand_set else legal_moves(board)


def fast_best_move(board, ai, human, K, max_depth=4, eval_fn=evaluate, use_forcing=True):
    """High-performance search for larger boards with neighborhood candidate pruning."""
    R, C = len(board), len(board[0])
    start = time.perf_counter()

    # 1. Opening instant response on empty board (center is mathematically dominant in m,n,k games)
    occupied = [(r, c) for r in range(R) for c in range(C) if board[r][c] != EMPTY]
    if not occupied:
        return (R // 2, C // 2), 0, time.perf_counter() - start, 1

    # 2. When human plays 1 stone on large board, play center immediately if open
    if len(occupied) == 1 and R * C >= 36:
        center = (R // 2, C // 2)
        if board[center[0]][center[1]] == EMPTY:
            return center, 0, time.perf_counter() - start, 1

    tr = ThreatTracker(board, K, (ai, human), EMPTY)
    W = make_weights(K)
    eval_f = partial(eval_fn, W=W)

    # 3. 0ms Immediate Tactical Wins and Blocks
    mine = tr.win_cells(ai)
    if mine:
        return divmod(next(iter(mine)), C), 1000000 - 1, time.perf_counter() - start, 1

    theirs = tr.win_cells(human)
    if len(theirs) == 1:
        return divmod(next(iter(theirs)), C), 0, time.perf_counter() - start, 1

    # 4. For smaller boards (<= 5x5), standard search is already instantaneous
    if R * C <= 25:
        return best_move(board, ai, human, K, max_depth, eval_fn, use_forcing)

    # 5. For larger boards (6x6+), prune distant candidates outside neighborhood radius
    max_branch = 14 if R * C >= 64 else 18
    raw_cands = get_optimized_candidates(board, max_dist=2)
    ranked = rank_candidates(board, raw_cands, ai, human, K)
    moves = ranked[:max_branch] if len(ranked) > max_branch else ranked

    nodes_visited = 0

    def _alphabeta(b, depth, lo, hi, maximizing, last):
        nonlocal nodes_visited
        nodes_visited += 1

        mover = human if maximizing else ai
        to_move = ai if maximizing else human
        forced = None

        if use_forcing:
            if tr.win_cells(to_move):
                return (1000000 - depth - 1) if to_move == ai else (depth + 1 - 1000000)
            opp_wins = tr.win_cells(mover)
            if len(opp_wins) >= 2:
                return (1000000 - depth - 2) if mover == ai else (depth + 2 - 1000000)
            if len(opp_wins) == 1:
                forced = [divmod(next(iter(opp_wins)), C)]

        if depth >= max_depth:
            return eval_f(tr, ai, human, K, to_move, depth)

        if forced:
            cands = forced
        else:
            c = get_optimized_candidates(b, max_dist=2)
            r_cands = rank_candidates(b, c, to_move, mover, K)
            cands = r_cands[:max_branch] if len(r_cands) > max_branch else r_cands

        if not cands:
            return 0

        if maximizing:
            val = -math.inf
            for mr, mc in cands:
                b[mr][mc] = ai
                tr.place(mr, mc, ai)
                val = max(val, _alphabeta(b, depth + 1, lo, hi, False, (mr, mc)))
                tr.undo(mr, mc, ai)
                b[mr][mc] = EMPTY
                lo = max(lo, val)
                if lo >= hi:
                    break
            return val
        else:
            val = math.inf
            for mr, mc in cands:
                b[mr][mc] = human
                tr.place(mr, mc, human)
                val = min(val, _alphabeta(b, depth + 1, lo, hi, True, (mr, mc)))
                tr.undo(mr, mc, human)
                b[mr][mc] = EMPTY
                hi = min(hi, val)
                if lo >= hi:
                    break
            return val

    best_val = -math.inf
    best_moves = []
    tol = 1e-6

    for r, c in moves:
        board[r][c] = ai
        tr.place(r, c, ai)
        lo = best_val - 2 * tol if best_val > -math.inf else -math.inf
        val = _alphabeta(board, 1, lo, math.inf, False, (r, c))
        tr.undo(r, c, ai)
        board[r][c] = EMPTY

        if val > best_val + tol:
            best_val = val
            best_moves = [(r, c)]
        elif math.isclose(val, best_val, rel_tol=0.0, abs_tol=tol):
            best_moves.append((r, c))

    best = best_moves[0] if best_moves else moves[0]
    elapsed = time.perf_counter() - start
    return best, best_val, elapsed, nodes_visited


class TicTacToeUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Dynamic Tic-Tac-Toe")
        self.root.geometry("760x820")
        self.root.minsize(560, 640)
        self.root.configure(bg="#F8FAFC")

        # Use 'clam' theme so buttons, entries, and spinboxes render consistently on macOS
        self.style = ttk.Style()
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")

        # Start Game button style: same color palette as standard buttons, with flat square corners
        self.style.configure(
            "Start.TButton",
            font=("Helvetica", 12, "bold"),
            padding=(20, 10),
        )

        # Configuration Variables (matching main.py prompts)
        self.mode_var = tk.StringVar(value="Human (X) vs AI (O)")
        self.r_var = tk.StringVar(value="3")
        self.c_var = tk.StringVar(value="3")
        self.k_var = tk.StringVar(value="3")
        self.depth_var = tk.StringVar(value="4")
        self.forcing_var = tk.BooleanVar(value=True)

        # Active game state
        self.R = 3
        self.C = 3
        self.K = 3
        self.max_depth = 4
        self.use_forcing = True
        self.mode = "h_vs_ai"  # 'h_vs_ai', 'ai_vs_h', 'h_vs_h'

        self.board = []
        self.turn = "X"
        self.game_over = False
        self.ai_thinking = False
        self.move_history = []
        self.winning_cells = []
        self.hover_cell = None
        self.cell_rects = {}
        self.game_id = 0

        # Thread-safe AI queue
        self.ai_queue = queue.Queue()
        self._poll_ai_queue()

        # Views
        self.setup_frame = tk.Frame(self.root, bg="#F8FAFC")
        self.game_frame = tk.Frame(self.root, bg="#F8FAFC")

        self._build_setup_view()
        self._build_game_view()

        # Show configuration screen first at startup
        self.show_setup_view()

    # =========================================================================
    # VIEW 1: INITIAL CONFIGURATION SCREEN (Shown at First Run)
    # =========================================================================
    def _build_setup_view(self):
        self.card = tk.Frame(
            self.setup_frame,
            bg="#FFFFFF",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            padx=32,
            pady=28,
        )
        self.card.pack(expand=True, padx=20, pady=20)
        card = self.card

        tk.Label(
            card,
            text="Dynamic Tic-Tac-Toe",
            bg="#FFFFFF",
            fg="#0F172A",
            font=("Helvetica", 20, "bold"),
        ).pack(anchor=tk.W, pady=(0, 4))

        tk.Label(
            card,
            text="Configure board dimensions, winning length, and AI parameters:",
            bg="#FFFFFF",
            fg="#475569",
            font=("Helvetica", 11),
        ).pack(anchor=tk.W, pady=(0, 16))

        # Quick Presets Row (Clean 4-column grid ensuring all buttons, including 9x9, fit with zero clipping)
        preset_frame = tk.Frame(card, bg="#FFFFFF")
        preset_frame.pack(fill=tk.X, pady=(0, 16))
        tk.Label(
            preset_frame,
            text="Quick Presets:",
            bg="#FFFFFF",
            fg="#334155",
            font=("Helvetica", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 6))

        btn_grid = tk.Frame(preset_frame, bg="#FFFFFF")
        btn_grid.pack(fill=tk.X)
        for i in range(4):
            btn_grid.columnconfigure(i, weight=1, uniform="presets")

        for i, (label, (r, c, k, d)) in enumerate([
            ("3x3 (K=3)", (3, 3, 3, 4)),
            ("5x5 (K=4)", (5, 5, 4, 4)),
            ("7x7 (K=4)", (7, 7, 4, 3)),
            ("9x9 (K=5)", (9, 9, 5, 3)),
        ]):
            btn = ttk.Button(
                btn_grid,
                text=label,
                command=lambda r=r, c=c, k=k, d=d: self._fill_preset(r, c, k, d),
            )
            btn.grid(row=0, column=i, padx=3, sticky="ew")

        # Form Fields Grid
        form = tk.Frame(card, bg="#FFFFFF")
        form.pack(fill=tk.X, pady=4)
        form.columnconfigure(1, weight=1)

        # 1. Game Mode
        tk.Label(
            form,
            text="Game Mode:",
            bg="#FFFFFF",
            fg="#1E293B",
            font=("Helvetica", 11, "bold"),
        ).grid(row=0, column=0, sticky=tk.W, pady=8, padx=(0, 16))

        mode_combo = ttk.Combobox(
            form,
            textvariable=self.mode_var,
            state="readonly",
            font=("Helvetica", 11),
            values=[
                "Human (X) vs AI (O)",
                "AI (X) vs Human (O)",
                "Human (X) vs Player (O)",
            ],
        )
        mode_combo.grid(row=0, column=1, sticky=tk.EW, pady=8)

        # 2. Rows (R)
        tk.Label(
            form,
            text="Rows (R):",
            bg="#FFFFFF",
            fg="#1E293B",
            font=("Helvetica", 11, "bold"),
        ).grid(row=1, column=0, sticky=tk.W, pady=8, padx=(0, 16))

        r_spin = ttk.Spinbox(form, from_=1, to=20, textvariable=self.r_var, font=("Helvetica", 11))
        r_spin.grid(row=1, column=1, sticky=tk.EW, pady=8)

        # 3. Columns (C)
        tk.Label(
            form,
            text="Columns (C):",
            bg="#FFFFFF",
            fg="#1E293B",
            font=("Helvetica", 11, "bold"),
        ).grid(row=2, column=0, sticky=tk.W, pady=8, padx=(0, 16))

        c_spin = ttk.Spinbox(form, from_=1, to=20, textvariable=self.c_var, font=("Helvetica", 11))
        c_spin.grid(row=2, column=1, sticky=tk.EW, pady=8)

        # 4. Consecutive marks to win (K)
        tk.Label(
            form,
            text="Consecutive to win (K):",
            bg="#FFFFFF",
            fg="#1E293B",
            font=("Helvetica", 11, "bold"),
        ).grid(row=3, column=0, sticky=tk.W, pady=8, padx=(0, 16))

        k_spin = ttk.Spinbox(form, from_=1, to=20, textvariable=self.k_var, font=("Helvetica", 11))
        k_spin.grid(row=3, column=1, sticky=tk.EW, pady=8)

        # 5. Search depth (default 4)
        tk.Label(
            form,
            text="Search depth (default 4):",
            bg="#FFFFFF",
            fg="#1E293B",
            font=("Helvetica", 11, "bold"),
        ).grid(row=4, column=0, sticky=tk.W, pady=8, padx=(0, 16))

        d_spin = ttk.Spinbox(form, from_=1, to=10, textvariable=self.depth_var, font=("Helvetica", 11))
        d_spin.grid(row=4, column=1, sticky=tk.EW, pady=8)

        # 6. Enable tactical forcing? (y/n)
        tk.Label(
            form,
            text="Tactical forcing:",
            bg="#FFFFFF",
            fg="#1E293B",
            font=("Helvetica", 11, "bold"),
        ).grid(row=5, column=0, sticky=tk.W, pady=8, padx=(0, 16))

        forcing_chk = tk.Checkbutton(
            form,
            text="Enable tactical forcing (recommended)",
            variable=self.forcing_var,
            bg="#FFFFFF",
            fg="#1E293B",
            activebackground="#FFFFFF",
            font=("Helvetica", 11),
        )
        forcing_chk.grid(row=5, column=1, sticky=tk.W, pady=8)

        # Validation Error Label
        self.error_label = tk.Label(
            card,
            text="",
            bg="#FFFFFF",
            fg="#DC2626",
            font=("Helvetica", 10, "bold"),
        )
        self.error_label.pack(anchor=tk.W, pady=(8, 4))

        # Start Game Button (Matches standard button color with flat square corners)
        start_btn = ttk.Button(
            card,
            text="Start Game  →",
            command=self.validate_and_start_game,
            style="Start.TButton",
            cursor="hand2",
        )
        start_btn.pack(fill=tk.X, pady=(12, 0))

    def _fill_preset(self, r, c, k, d):
        self.r_var.set(str(r))
        self.c_var.set(str(c))
        self.k_var.set(str(k))
        self.depth_var.set(str(d))
        self.error_label.config(text="")

    def _apply_preset_and_start(self, r, c, k, d):
        self._fill_preset(r, c, k, d)
        self.validate_and_start_game()

    def show_setup_view(self):
        self.game_id += 1  # cancel any running AI search
        self.ai_thinking = False
        self.game_frame.pack_forget()
        self.error_label.config(text="")
        # Keep input variables in sync with active game parameters
        self.r_var.set(str(self.R))
        self.c_var.set(str(self.C))
        self.k_var.set(str(self.K))
        self.depth_var.set(str(self.max_depth))
        self.forcing_var.set(self.use_forcing)
        self.setup_frame.pack(fill=tk.BOTH, expand=True)
        self.setup_frame.lift()
        if hasattr(self, "card"):
            self.card.lift()
        self.root.update_idletasks()
        self.root.bind("<Return>", lambda _e: self.validate_and_start_game())

    def validate_and_start_game(self):
        try:
            R = int(self.r_var.get().strip())
            C = int(self.c_var.get().strip())
            K = int(self.k_var.get().strip())
            depth_raw = self.depth_var.get().strip()
            max_depth = int(depth_raw if depth_raw else "4")
        except ValueError:
            self.error_label.config(text="Please enter valid integers.")
            return

        if R < 1 or C < 1 or not (1 <= K <= max(R, C)):
            self.error_label.config(text="Invalid dimensions or K (must satisfy 1 <= K <= max(R, C)).")
            return

        if max_depth < 1:
            self.error_label.config(text="Search depth must be at least 1.")
            return

        self.R, self.C, self.K = R, C, K
        self.max_depth = max_depth
        self.use_forcing = bool(self.forcing_var.get())
        self.mode = self._parse_mode()
        self.board = [[EMPTY] * self.C for _ in range(self.R)]

        self.root.unbind("<Return>")
        self.setup_frame.pack_forget()
        self.game_frame.pack(fill=tk.BOTH, expand=True)
        self.game_frame.lift()
        self.root.update_idletasks()

        self.start_new_game()

    # =========================================================================
    # VIEW 2: ACTIVE GAME BOARD SCREEN
    # =========================================================================
    def _build_game_view(self):
        # Top Action Bar with 2 clean rows ensuring all buttons & labels fit without clipping
        top_bar = tk.Frame(self.game_frame, bg="#FFFFFF", bd=1, relief=tk.SOLID)
        top_bar.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(14, 6))

        # Row 1: Config summary label (left) & Actions (right: Undo, Restart, Configure Settings)
        row1 = tk.Frame(top_bar, bg="#FFFFFF")
        row1.pack(fill=tk.X, padx=12, pady=(8, 4))

        self.config_summary_label = tk.Label(
            row1,
            text="",
            bg="#FFFFFF",
            fg="#1E293B",
            font=("Helvetica", 11, "bold"),
        )
        self.config_summary_label.pack(side=tk.LEFT)

        actions_frame = tk.Frame(row1, bg="#FFFFFF")
        actions_frame.pack(side=tk.RIGHT)

        ttk.Button(
            actions_frame,
            text="↶ Undo",
            command=self.undo_move,
        ).pack(side=tk.LEFT, padx=3)

        ttk.Button(
            actions_frame,
            text="↻ Restart",
            command=self.start_new_game,
        ).pack(side=tk.LEFT, padx=3)

        ttk.Button(
            actions_frame,
            text="⚙ Configure Settings",
            command=self.show_setup_view,
        ).pack(side=tk.LEFT, padx=(3, 0))

        # Row 2: Quick Presets bar
        row2 = tk.Frame(top_bar, bg="#FFFFFF")
        row2.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Label(
            row2,
            text="Quick Presets:",
            bg="#FFFFFF",
            fg="#64748B",
            font=("Helvetica", 9, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 6))

        for label, (r, c, k, d) in [
            ("3x3 (K=3)", (3, 3, 3, 4)),
            ("5x5 (K=4)", (5, 5, 4, 4)),
            ("7x7 (K=4)", (7, 7, 4, 3)),
            ("9x9 (K=5)", (9, 9, 5, 3)),
        ]:
            ttk.Button(
                row2,
                text=label,
                command=lambda r=r, c=c, k=k, d=d: self._apply_preset_and_start(r, c, k, d),
            ).pack(side=tk.LEFT, padx=3)

        # Status & AI Telemetry Banner
        status_frame = tk.Frame(self.game_frame, bg="#EFF6FF", bd=1, relief=tk.SOLID)
        status_frame.pack(side=tk.TOP, fill=tk.X, padx=14, pady=6)

        self.status_label = tk.Label(
            status_frame,
            text="Ready",
            bg="#EFF6FF",
            fg="#1E3A8A",
            font=("Helvetica", 13, "bold"),
            pady=6,
        )
        self.status_label.pack(side=tk.TOP, fill=tk.X)

        self.stats_label = tk.Label(
            status_frame,
            text="",
            bg="#EFF6FF",
            fg="#475569",
            font=("Menlo", 10),
            pady=4,
        )
        self.stats_label.pack(side=tk.TOP, fill=tk.X)

        # Board Canvas
        canvas_container = tk.Frame(self.game_frame, bg="#F8FAFC")
        canvas_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=14, pady=(6, 14))

        self.canvas = tk.Canvas(
            canvas_container,
            bg="#FFFFFF",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Configure>", lambda _e: self.draw_board())
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Leave>", self.on_canvas_leave)

    def _parse_mode(self):
        val = self.mode_var.get()
        if "Human (X) vs AI (O)" in val:
            return "h_vs_ai"
        if "AI (X) vs Human (O)" in val:
            return "ai_vs_h"
        return "h_vs_h"

    def is_ai_turn(self):
        if self.mode == "h_vs_ai":
            return self.turn == "O"
        if self.mode == "ai_vs_h":
            return self.turn == "X"
        return False

    def start_new_game(self):
        self.game_id += 1
        self.board = [[EMPTY] * self.C for _ in range(self.R)]
        self.turn = "X"
        self.game_over = False
        self.ai_thinking = False
        self.move_history = []
        self.winning_cells = []
        self.hover_cell = None

        mode_str = self.mode_var.get()
        if self.mode == "h_vs_h":
            self.config_summary_label.config(
                text=f"{mode_str}  |  Board: {self.R}×{self.C}  |  Win K={self.K}"
            )
            self.stats_label.config(text="2-Player Mode: Take turns clicking on the board.")
        else:
            forcing_str = "ON" if self.use_forcing else "OFF"
            self.config_summary_label.config(
                text=f"{mode_str}  |  {self.R}×{self.C} (K={self.K})  |  Depth={self.max_depth}  |  Forcing={forcing_str}"
            )
            self.stats_label.config(text="Waiting for AI move...")

        self.update_status_banner()
        self.draw_board()

        if self.is_ai_turn():
            self.trigger_ai_move()

    def undo_move(self):
        if self.ai_thinking or not self.move_history:
            return

        steps = 2 if (self.mode in ("h_vs_ai", "ai_vs_h") and len(self.move_history) >= 2) else 1
        for _ in range(steps):
            if self.move_history:
                r, c, mark = self.move_history.pop()
                self.board[r][c] = EMPTY
                self.turn = mark

        self.game_over = False
        self.winning_cells = []
        self.update_status_banner()
        self.draw_board()

        if self.is_ai_turn():
            self.trigger_ai_move()

    def update_status_banner(self):
        if self.game_over:
            return
        if self.is_ai_turn():
            self.status_label.config(text=f"AI ({self.turn}) is thinking...", fg="#B45309")
        else:
            if self.mode == "h_vs_h":
                self.status_label.config(
                    text=f"Player {self.turn}'s Turn — Click an empty cell (1-{self.R}, 1-{self.C})",
                    fg="#1E3A8A",
                )
            else:
                self.status_label.config(
                    text=f"Your Turn ({self.turn}) — Click an empty cell (1-{self.R}, 1-{self.C})",
                    fg="#1E3A8A",
                )

    def _board_geometry(self):
        w = max(self.canvas.winfo_width(), 100)
        h = max(self.canvas.winfo_height(), 100)
        margin = 38
        avail_w = max(w - 2 * margin, 50)
        avail_h = max(h - 2 * margin, 50)
        cell_size = min(avail_w / self.C, avail_h / self.R)
        grid_w = cell_size * self.C
        grid_h = cell_size * self.R
        x0 = (w - grid_w) / 2
        y0 = (h - grid_h) / 2
        return x0, y0, cell_size

    def pixel_to_cell(self, x, y):
        x0, y0, cell_size = self._board_geometry()
        c = int((x - x0) // cell_size)
        r = int((y - y0) // cell_size)
        if 0 <= r < self.R and 0 <= c < self.C:
            return r, c
        return None

    def _get_cell_color(self, r, c, win_set=None, last_move=None):
        if win_set is None:
            win_set = set(self.winning_cells)
        if last_move is None:
            last_move = self.move_history[-1][:2] if self.move_history else None

        if (r, c) in win_set:
            return "#DCFCE7"
        if (r, c) == last_move:
            return "#FEF9C3"
        if self.hover_cell == (r, c) and self.board[r][c] == EMPTY:
            return "#F1F5F9"
        return "#FFFFFF"

    def _update_hover(self, new_cell):
        if new_cell == self.hover_cell:
            return
        old_cell = self.hover_cell
        self.hover_cell = new_cell
        win_set = set(self.winning_cells)
        last_move = self.move_history[-1][:2] if self.move_history else None

        if old_cell and old_cell in self.cell_rects:
            or_, oc_ = old_cell
            self.canvas.itemconfigure(
                self.cell_rects[old_cell],
                fill=self._get_cell_color(or_, oc_, win_set, last_move),
            )
        if new_cell and new_cell in self.cell_rects:
            nr_, nc_ = new_cell
            self.canvas.itemconfigure(
                self.cell_rects[new_cell],
                fill=self._get_cell_color(nr_, nc_, win_set, last_move),
            )

    def on_canvas_motion(self, event):
        if self.game_over or self.ai_thinking or self.is_ai_turn():
            if self.hover_cell is not None:
                self._update_hover(None)
            return
        cell = self.pixel_to_cell(event.x, event.y)
        if cell != self.hover_cell:
            self._update_hover(cell)

    def on_canvas_leave(self, _event):
        if self.hover_cell is not None:
            self._update_hover(None)

    def on_canvas_click(self, event):
        if self.game_over or self.ai_thinking or self.is_ai_turn():
            return
        cell = self.pixel_to_cell(event.x, event.y)
        if cell is None:
            return
        r, c = cell
        if r >= len(self.board) or c >= len(self.board[0]) or self.board[r][c] != EMPTY:
            return

        self.apply_move(r, c, self.turn)
        if not self.game_over and self.is_ai_turn():
            self.trigger_ai_move()

    def apply_move(self, r, c, mark):
        self.board[r][c] = mark
        self.move_history.append((r, c, mark))
        self.hover_cell = None

        if check_win(self.board, r, c, mark, self.K):
            self.game_over = True
            self.winning_cells = find_winning_cells(self.board, r, c, mark, self.K)
            if self.mode == "h_vs_h":
                winner_text = f"Player {mark} Wins!"
            elif (self.mode == "h_vs_ai" and mark == "X") or (self.mode == "ai_vs_h" and mark == "O"):
                winner_text = f"Human ({mark}) Wins!"
            else:
                winner_text = f"AI ({mark}) Wins!"
            self.status_label.config(text=winner_text, fg="#15803D")
            self.draw_board()
            return

        if not legal_moves(self.board):
            self.game_over = True
            self.status_label.config(text="Draw!", fg="#475569")
            self.draw_board()
            return

        self.turn = OTHER[mark]
        self.update_status_banner()
        self.draw_board()

    def trigger_ai_move(self):
        self.ai_thinking = True
        self.update_status_banner()
        self.draw_board()

        current_game_id = self.game_id
        board_copy = [row[:] for row in self.board]
        ai_mark = self.turn
        human_mark = OTHER[ai_mark]
        K = self.K
        max_depth = self.max_depth
        use_forcing = self.use_forcing

        def worker():
            move, score, elapsed, nodes = fast_best_move(
                board_copy,
                ai=ai_mark,
                human=human_mark,
                K=K,
                max_depth=max_depth,
                eval_fn=evaluate,
                use_forcing=use_forcing,
            )
            self.ai_queue.put((current_game_id, move, score, elapsed, nodes, ai_mark))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_ai_queue(self):
        try:
            while True:
                item = self.ai_queue.get_nowait()
                game_id, move, score, elapsed, nodes, ai_mark = item
                self._on_ai_done(game_id, move, score, elapsed, nodes, ai_mark)
        except queue.Empty:
            pass
        self.root.after(20, self._poll_ai_queue)

    def _on_ai_done(self, game_id, move, score, elapsed, nodes, ai_mark):
        if game_id != self.game_id or self.game_over:
            return
        self.ai_thinking = False

        if move is None:
            self.game_over = True
            self.status_label.config(text="Draw!", fg="#475569")
            self.draw_board()
            return

        r, c = move
        throughput = nodes / elapsed if elapsed > 0 else 0
        self.stats_label.config(
            text=(
                f"AI plays row {r + 1}, col {c + 1} | Score: {score} | "
                f"Time: {elapsed:.4f}s | Nodes: {nodes:,} | "
                f"Throughput: {throughput:,.0f} nodes/s"
            )
        )
        self.apply_move(r, c, ai_mark)

    def draw_board(self):
        if not self.board or len(self.board) != self.R or (self.board and len(self.board[0]) != self.C):
            return
        self.canvas.delete("all")
        x0, y0, cell_size = self._board_geometry()

        last_move = self.move_history[-1][:2] if self.move_history else None
        win_set = set(self.winning_cells)

        header_font_size = max(8, min(12, int(cell_size * 0.22)))
        for c in range(self.C):
            cx = x0 + (c + 0.5) * cell_size
            self.canvas.create_text(
                cx,
                y0 - 16,
                text=str(c + 1),
                fill="#64748B",
                font=("Helvetica", header_font_size, "bold"),
            )
        for r in range(self.R):
            cy = y0 + (r + 0.5) * cell_size
            self.canvas.create_text(
                x0 - 16,
                cy,
                text=str(r + 1),
                fill="#64748B",
                font=("Helvetica", header_font_size, "bold"),
            )

        self.cell_rects = {}
        for r in range(self.R):
            for c in range(self.C):
                x1 = x0 + c * cell_size
                y1 = y0 + r * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size

                bg_color = self._get_cell_color(r, c, win_set, last_move)

                rect_id = self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=bg_color, outline="#CBD5E1", width=1.5
                )
                self.cell_rects[(r, c)] = rect_id

                val = self.board[r][c]
                pad = cell_size * 0.22
                stroke = max(2, int(cell_size * 0.09))

                if val == "X":
                    self.canvas.create_line(
                        x1 + pad,
                        y1 + pad,
                        x2 - pad,
                        y2 - pad,
                        fill="#2563EB",
                        width=stroke,
                        capstyle=tk.ROUND,
                    )
                    self.canvas.create_line(
                        x1 + pad,
                        y2 - pad,
                        x2 - pad,
                        y1 + pad,
                        fill="#2563EB",
                        width=stroke,
                        capstyle=tk.ROUND,
                    )
                elif val == "O":
                    self.canvas.create_oval(
                        x1 + pad, y1 + pad, x2 - pad, y2 - pad, outline="#DC2626", width=stroke
                    )

        if len(self.winning_cells) >= 2:
            r_start, c_start = self.winning_cells[0]
            r_end, c_end = self.winning_cells[-1]
            sx = x0 + (c_start + 0.5) * cell_size
            sy = y0 + (r_start + 0.5) * cell_size
            ex = x0 + (c_end + 0.5) * cell_size
            ey = y0 + (r_end + 0.5) * cell_size
            self.canvas.create_line(
                sx,
                sy,
                ex,
                ey,
                fill="#16A34A",
                width=max(4, int(cell_size * 0.11)),
                capstyle=tk.ROUND,
            )


def launch_ui():
    root = tk.Tk()
    TicTacToeUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_ui()
