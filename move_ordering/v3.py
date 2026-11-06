from engine.rules import *

_ORDER = {}

def _center_order(R, C):
    cr = (R - 1) / 2
    cc = (C - 1) / 2
    return sorted(
        ((r, c) for r in range(R) for c in range(C)),
        key=lambda p: (abs(p[0] - cr) + abs(p[1] - cc), -p[0], -p[1]),
    )

def rank_candidates(board, tr, me, opp):
    """Center-first empties, with the tracker's win/block cells moved to the front."""
    R, C = len(board), len(board[0])
    order = _ORDER.get((R, C))
    if order is None:
        order = _ORDER[(R, C)] = _center_order(R, C)

    moves = [(r, c) for r, c in order if board[r][c] == EMPTY]

    hot = list({
        divmod(x, C)
        for x in (*tr.win_cells(me), *tr.win_cells(opp))
    })
    
    if hot:
        hot_set = set(hot)
        moves = hot + [m for m in moves if m not in hot_set]
    return moves