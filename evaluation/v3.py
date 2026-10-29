from engine.rules import *

class ThreatTracker:
    def __init__(self, board, K, players, empty):
        # players = (ai, human); DIRS is your existing direction list
        self.R, self.C, self.K = len(board), len(board[0]), K
        R, C = self.R, self.C
        self.pid = {players[0]: 0, players[1]: 1}

        self.window_cells = []
        self.cell_wins = [[] for _ in range(R * C)]

        for dr, dc in DIRS:
            for r in range(R):
                for c in range(C):
                    er = r + (K - 1) * dr
                    ec = c + (K - 1) * dc

                    if not (0 <= er < R and 0 <= ec < C):
                        continue

                    cells = [
                        (r + k * dr) * C + (c + k * dc)
                        for k in range(K)
                    ]

                    wid = len(self.window_cells)
                    self.window_cells.append(cells)

                    for cell in cells:
                        self.cell_wins[cell].append(wid)

        W = len(self.window_cells)

        self.esum = [0] * W
        self.cnt = [[0] * W for _ in range(2)]
        self.tally = [[0] * (K + 1) for _ in range(2)]
        self.threat = [{}, {}]

        for w, cells in enumerate(self.window_cells):
            for cell in cells:
                r, c = divmod(cell, C)
                value = board[r][c]

                if value == empty:
                    self.esum[w] += cell
                else:
                    p = self.pid[value]
                    self.cnt[p][w] += 1

            for p in (0, 1):
                if self.cnt[1 - p][w] != 0:
                    continue

                n = self.cnt[p][w]
                self.tally[p][n] += 1

                if n == K - 1:
                    cell = self.esum[w]
                    self.threat[p][cell] = (
                        self.threat[p].get(cell, 0) + 1
                    )

    def _remove(self, w):
        K, cnt = self.K, self.cnt
        for p in (0, 1):
            if cnt[1 - p][w] == 0:
                n = cnt[p][w]
                self.tally[p][n] -= 1
                if n == K - 1:
                    t, cell = self.threat[p], self.esum[w]
                    t[cell] -= 1
                    if t[cell] == 0:
                        del t[cell]

    def _add(self, w):
        K, cnt = self.K, self.cnt
        for p in (0, 1):
            if cnt[1 - p][w] == 0:
                n = cnt[p][w]
                self.tally[p][n] += 1
                if n == K - 1:
                    t, cell = self.threat[p], self.esum[w]
                    t[cell] = t.get(cell, 0) + 1

    def place(self, r, c, player):
        p, cell = self.pid[player], r * self.C + c
        for w in self.cell_wins[cell]:
            self._remove(w)
            self.cnt[p][w] += 1
            self.esum[w] -= cell
            self._add(w)

    def undo(self, r, c, player):
        p, cell = self.pid[player], r * self.C + c
        for w in self.cell_wins[cell]:
            self._remove(w)
            self.cnt[p][w] -= 1
            self.esum[w] += cell
            self._add(w)

    # --- O(1) queries ---
    def win_cells(self, player):                    # cells where player wins now
        return self.threat[self.pid[player]].keys()

    def has_open_k1(self, player):                  # >= 2 distinct completion cells
        return len(self.threat[self.pid[player]]) >= 2

    def windows(self, player, n):                   # live windows with n stones
        return self.tally[self.pid[player]][n]

def threat_after(tr, r, c, player):
    tr.place(r, c, player)
    out = (
        len(tr.win_cells(player)),          # distinct completion cells created
        tr.windows(player, tr.K - 1),       # K-1 windows
        tr.windows(player, tr.K - 2),       # K-2 windows
    )     
    tr.undo(r, c, player)
    return out

def hard_rules(tr, board, me, opp):
    """Returns (kind, move) with kind in {'win','block','lost','forced_win'}, or (None, None)."""
    C = tr.C

    mine = tr.win_cells(me)
    if mine:
        return 'win', divmod(next(iter(mine)), C)

    theirs = tr.win_cells(opp)
    if len(theirs) == 1:
        return 'block', divmod(next(iter(theirs)), C)
    
    if len(theirs) >= 2:
        return 'lost', divmod(next(iter(theirs)), C)

    # no immediate threats either way: look for a double threat
    for r in range(tr.R):
        for c in range(tr.C):
            if board[r][c] != EMPTY:
                continue

            wins, _, _ = threat_after(tr, r, c, me)

            if wins >= 2:
                return 'forced_win', (r, c)
            
    return None, None

BASE   = 8      # ratio between consecutive stone counts
TEMPO  = 1.5    # multiplier on the side to move's potential
DEFEND = 1.1    # weight on the opponent's potential, from the AI's view

def make_weights(K, ratio=None):
    r = ratio or 4 * K
    W, w = [0] * K, 1
    for n in range(1, K):
        W[n] = w
        w *= r
    return W

def pattern_score(tr, p, W):
    t = tr.tally[tr.pid[p]]
    return sum(W[n] * t[n] for n in range(1, tr.K))

def evaluate(tr, ai, human, K, to_move, depth, W):
    other = human if to_move == ai else ai

    # Exact tactics (normally caught earlier, kept as a safety net)
    if tr.win_cells(to_move):
        return (WIN - depth - 1) if to_move == ai else (depth + 1 - WIN)

    if len(tr.win_cells(other)) >= 2:
        return (WIN - depth - 2) if other == ai else (depth + 2 - WIN)

    s_ai = pattern_score(tr, ai, W)
    s_human = pattern_score(tr, human, W)

    if to_move == ai:
        s_ai *= TEMPO
    else:
        s_human *= TEMPO

    # A single forcing threat: the side to move must answer it
    if tr.win_cells(other):
        if other == ai:
            s_ai *= 2
        else:
            s_human *= 2

    return s_ai - DEFEND * s_human
