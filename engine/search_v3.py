import math
import time
import random
from functools import partial

from engine.rules import *
from evaluation.v3 import ThreatTracker, evaluate, make_weights
from move_ordering.v2 import rank_candidates

TOL = 1e-6

def static_delta(tr, r, c, me, opp, W):
    K, cell = tr.K, r * tr.C + c
    pm = tr.pid[me]
    po = tr.pid[opp]
    gain = kill = 0
    for w in tr.cell_wins[cell]:
        cm = tr.cnt[pm][w]
        co = tr.cnt[po][w]
        if co == 0:                          # live for me: window grows
            gain += W[min(cm + 1, K - 1)] - W[cm]
        if cm == 0 and co:                   # live for opp: window dies
            kill += W[co]
    return gain + kill

def pick_among_ties(tr, board, ties, me, opp, W, rng):
    scored = [
        (static_delta(tr, r, c, me, opp, W), (r, c))
        for r, c in ties
    ]

    best_delta = max(delta for delta, move in scored)

    return rng.choice([
        move for delta, move in scored
        if delta == best_delta
    ])

def alphabeta(board, depth, max_depth, alpha, beta, maximizing,
              ai, human, K, last, eval_fn, tr, use_forcing=True):
    global nodes_visited
    nodes_visited += 1

    r, c = last
    mover   = human if maximizing else ai        # who just moved
    to_move = ai if maximizing else human
    forced = None

    if use_forcing:
        # step 3: exact tactical outcomes, before the depth cutoff
        if tr.win_cells(to_move):
            return (WIN - depth - 1) if to_move == ai else (depth + 1 - WIN)
        theirs = tr.win_cells(mover)
        if len(theirs) >= 2:
            return (WIN - depth - 2) if mover == ai else (depth + 2 - WIN)
        if len(theirs) == 1:
            forced = [divmod(next(iter(theirs)), tr.C)]

    if depth >= max_depth:
        return eval_fn(tr, ai, human, K, to_move, depth)

    # moves = legal_moves(board)
    moves = forced or rank_candidates(board, legal_moves(board), to_move, mover, K)
    if not moves:
        return 0

    if maximizing:
        value = -math.inf
        for (mr, mc) in moves:
            board[mr][mc] = ai
            tr.place(mr, mc, ai)
            value = max(value, alphabeta(board, depth + 1, max_depth, alpha, beta,
                                         False, ai, human, K, (mr, mc),
                                         eval_fn, tr, use_forcing))
            tr.undo(mr, mc, ai)
            board[mr][mc] = EMPTY

            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value

    else:
        value = math.inf
        for (mr, mc) in moves:
            board[mr][mc] = human
            tr.place(mr, mc, human)
            value = min(value, alphabeta(board, depth + 1, max_depth, alpha, beta,
                                         True, ai, human, K, (mr, mc),
                                         eval_fn, tr, use_forcing))
            tr.undo(mr, mc, human)
            board[mr][mc] = EMPTY

            beta = min(beta, value)
            if alpha >= beta:
                break
        return value

def best_move_v1(board, ai, human, K, max_depth=4, eval_fn=evaluate,
              use_forcing=True, debug=False):
    global nodes_visited
    nodes_visited = 0

    start = time.perf_counter()

    tr = ThreatTracker(board, K, (ai, human), EMPTY)
    eval_fn = partial(eval_fn, W=make_weights(K))

    # root hard rules: one code path, the search confirms the result
    mine, theirs = tr.win_cells(ai), tr.win_cells(human)
    if mine:
        moves = [divmod(next(iter(mine)), tr.C)]
    elif len(theirs) == 1:
        moves = [divmod(next(iter(theirs)), tr.C)]
    else:
        moves = rank_candidates(board, legal_moves(board), ai, human, K)

    best, best_val = None, -math.inf
    alpha, beta = -math.inf, math.inf

    for (r, c) in moves:
        board[r][c] = ai
        tr.place(r, c, ai)

        val = alphabeta(board, 1, max_depth, alpha, beta, False,
                        ai, human, K, (r, c), eval_fn, tr, use_forcing)

        tr.undo(r, c, ai)
        board[r][c] = EMPTY

        if val > best_val:
            best_val, best = val, (r, c)
        alpha = max(alpha, best_val)

    if debug:   # the tracker must end exactly where it began
        fresh = ThreatTracker(board, K, (ai, human), EMPTY)
        assert (tr.cnt, tr.esum, tr.tally, tr.threat) == \
               (fresh.cnt, fresh.esum, fresh.tally, fresh.threat), "tracker drifted"

    elapsed = time.perf_counter() - start
    return best, best_val, elapsed, nodes_visited

def best_move_root(board, ai, human, K, max_depth=4, eval_fn=evaluate,
              use_forcing=True, debug=True, rng=None):
    global nodes_visited
    nodes_visited = 0

    start = time.perf_counter()

    if rng is None:
        rng = random.Random()

    tr = ThreatTracker(board, K, (ai, human), EMPTY)
    W = make_weights(K)
    eval_fn = partial(eval_fn, W=W)

    # Root tactical rules
    mine, theirs = tr.win_cells(ai), tr.win_cells(human)

    if mine:
        moves = [divmod(next(iter(mine)), tr.C)]
    elif len(theirs) == 1:
        moves = [divmod(next(iter(theirs)), tr.C)]
    else:
        moves = legal_moves(board)

    if not moves:
        return None, 0, time.perf_counter() - start, nodes_visited

    root_scores = []

    # Evaluate each root candidate independently.
    for r, c in moves:
        board[r][c] = ai
        tr.place(r, c, ai)

        val = alphabeta(
            board, 1, max_depth, -math.inf, math.inf, False,
            ai, human, K, (r, c), eval_fn, tr, use_forcing
        )

        tr.undo(r, c, ai)
        board[r][c] = EMPTY

        root_scores.append(((r, c), val))

    # Identify the best minimax score.
    best_val = max(val for move, val in root_scores)

    # Keep only moves whose scores tie for the best.
    ties = [
        move for move, val in root_scores
        if math.isclose(val, best_val, rel_tol=0.0, abs_tol=TOL)
    ]

    # Tiebreak only if multiple moves are equally good.
    if len(ties) == 1:
        best = ties[0]
    else:
        best = pick_among_ties(
            tr, board, ties, ai, human, W, rng
        )

    if debug:
        fresh = ThreatTracker(board, K, (ai, human), EMPTY)
        assert (tr.cnt, tr.esum, tr.tally, tr.threat) == (
            fresh.cnt, fresh.esum, fresh.tally, fresh.threat
        ), "tracker drifted"

    if debug:
        print("\nRoot candidate scores:")
        for (r, c), score in sorted(
            root_scores, key=lambda item: item[1], reverse=True
        )[:24]:
            print(f"  {(r + 1, c + 1)}: {score}")

        print("Tied best moves:", [
            (r + 1, c + 1) for r, c in ties
        ])
        print("Chosen move:", (best[0] + 1, best[1] + 1))

    elapsed = time.perf_counter() - start
    return best, best_val, elapsed, nodes_visited

def best_move(board, ai, human, K, max_depth=4, eval_fn=evaluate,
              use_forcing=True, debug=True, rng=None):
    global nodes_visited
    nodes_visited = 0

    start = time.perf_counter()

    if rng is None:
        rng = random.Random()

    tr = ThreatTracker(board, K, (ai, human), EMPTY)
    W = make_weights(K)
    eval_fn = partial(eval_fn, W=W)

    # Root tactical rules
    mine, theirs = tr.win_cells(ai), tr.win_cells(human)

    if mine:
        moves = [divmod(next(iter(mine)), tr.C)]
    elif len(theirs) == 1:
        moves = [divmod(next(iter(theirs)), tr.C)]
    else:
        moves = rank_candidates(board, legal_moves(board), ai, human, K)

    if not moves:
        elapsed = time.perf_counter() - start
        return None, 0, elapsed, nodes_visited

    root_scores = []
    best_val = -math.inf
    best_moves = []

    alpha, beta = -math.inf, math.inf

    for r, c in moves:
        board[r][c] = ai
        tr.place(r, c, ai)

        lo = best_val - 2 * TOL if best_val > -math.inf else -math.inf
        val = alphabeta(board, 1, max_depth, lo, math.inf, False,
                        ai, human, K, (r, c), eval_fn, tr, use_forcing)

        tr.undo(r, c, ai)
        board[r][c] = EMPTY

        root_scores.append(((r, c), val))

        if val > best_val + TOL:
            best_val = val
            best_moves = [(r, c)]
        elif math.isclose(val, best_val, rel_tol=0.0, abs_tol=TOL):
            best_moves.append((r, c))

        alpha = max(alpha, best_val)

    best = rng.choice(best_moves)

    if debug:
        print("\nRoot candidate scores:")
        for (r, c), score in sorted(
            root_scores, key=lambda item: item[1], reverse=True
        )[:24]:
            print(f"  {(r + 1, c + 1)}: {score}")

        print("Tied best moves:", [
            (r + 1, c + 1) for r, c in best_moves
        ])
        print("Chosen move:", (best[0] + 1, best[1] + 1))

    elapsed = time.perf_counter() - start
    return best, best_val, elapsed, nodes_visited
