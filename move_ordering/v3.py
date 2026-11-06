from engine.rules import *

_TABLES = {}

def _center_order(R, C):
    cr, cc = (R - 1) / 2, (C - 1) / 2
    return sorted(
        ((r, c) for r in range(R) for c in range(C)),
        key=lambda p: (abs(p[0] - cr) + abs(p[1] - cc), -p[0], -p[1]),
    )

def _tables(R, C, radius):
    key = (R, C, radius)
    t = _TABLES.get(key)
    if t is None:
        order = _center_order(R, C)
        pos = {m: i for i, m in enumerate(order)}
        nb = {}
        for r in range(R):
            for c in range(C):
                nb[(r, c)] = [
                    (r + dr, c + dc)
                    for dr in range(-radius, radius + 1)
                    for dc in range(-radius, radius + 1)
                    if (dr or dc) and 0 <= r + dr < R and 0 <= c + dc < C
                ]
        t = _TABLES[key] = (order, pos, nb)
    return t

def rank_candidates(board, tr, me, opp, radius=2):
    R, C = len(board), len(board[0])
    order, pos, nb = _tables(R, C, radius)

    cand, any_stone = set(), False
    for r in range(R):
        row = board[r]
        for c in range(C):
            if row[c] != EMPTY:
                any_stone = True
                cand.update(nb[(r, c)])

    if not any_stone:
        return [(R // 2, C // 2)]                      # same as legal_moves

    moves = sorted((m for m in cand if board[m[0]][m[1]] == EMPTY),
                   key=pos.__getitem__)
    if not moves:                                      # same rare fallback
        moves = [m for m in order if board[m[0]][m[1]] == EMPTY]

    hot = [divmod(x, C) for x in tr.win_cells(me)]
    hot += [divmod(x, C) for x in tr.win_cells(opp)]
    if hot:
        hot_set = set(hot)
        moves = hot + [m for m in moves if m not in hot_set]
    return moves