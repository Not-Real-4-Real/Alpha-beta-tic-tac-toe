import math
import random
import statistics

import os
from multiprocessing import Pool

from engine.rules import *
from evaluation.v3 import evaluate
from engine.search_v3 import *

OTHER = {'X': 'O', 'O': 'X'}

def _run_pair(job):
    """Top-level so it can be pickled. Plays one opening with colors swapped."""
    a, b, R, C, K, opening, seeds = job
    out = []
    for a_is_x, seed in zip((True, False), seeds):
        x, o = (a, b) if a_is_x else (b, a)
        winner, stats = play_game(R, C, K, x, o, opening, rng=random.Random(seed))
        out.append((a_is_x, winner, stats))
    return out

def print_board(board):
    """Print a dynamically sized, labeled board."""
    R, C = len(board), len(board[0])
    cell_width = max(3, len(str(C)) + 2)
    row_width = len(str(R))

    header = " " * (row_width + 1)
    header += "".join(
        f"{c:^{cell_width}}"
        for c in range(1, C + 1)
    )

    print(header)
    print(" " * (row_width + 1) + "-" * (C * cell_width))

    for r in range(R):
        cells = "".join(
            f"{value:^{cell_width}}"
            for value in board[r]
        )
        print(f"{r + 1:>{row_width}}|{cells}")

    print()

def get_move(agent, board, turn, K, rng):
    """
    Single place that knows best_move's signature.
    To support older versions later, give the agent its own 'move_fn'
    adapter that returns (move, value, elapsed, nodes).
    """
    move_fn = agent.get('move_fn', best_move)
    return move_fn(
        board,
        ai=turn,
        human=OTHER[turn],
        K=K,
        max_depth=agent['depth'],
        eval_fn=agent.get('eval', evaluate),
        use_forcing=agent.get('use_forcing', True),
        debug=False,          # no per-move printing / drift assert in tournaments
        rng=rng,
    )

def random_opening(R, C, plies, rng):
    """Random cells, alternating X/O. Keep plies <= 2*(K-1) so no one can win."""
    return rng.sample([(r, c) for r in range(R) for c in range(C)], plies)

def play_game(
    R, C, K, x_agent, o_agent, opening,
    rng=None, verbose=False, trace=False
):
    if rng is None:
        rng = random.Random()

    board = [[EMPTY] * C for _ in range(R)]
    agents = {'X': x_agent, 'O': o_agent}
    stats = {p: {'time': 0.0, 'nodes': 0, 'moves': 0} for p in 'XO'}

    turn = 'X'
    for r, c in opening:
        board[r][c] = turn
        turn = OTHER[turn]

    if verbose:
        print("\n" + "=" * 50)
        print(f"Game: X={x_agent['name']} vs O={o_agent['name']}")
        print(f"Opening moves: {len(opening)}")
        print("Initial board:")
        print_board(board)

    def finish(winner):
        if verbose:
            total_moves = len(opening) + sum(s['moves'] for s in stats.values())
            total_time = sum(s['time'] for s in stats.values())

            print("Final board:")
            print_board(board)
            print(f"Winner: {winner or 'Draw'}")
            print(f"Total moves: {total_moves}")
            print(f"Total AI search time: {total_time:.3f} s")

            for mark in 'XO':
                s = stats[mark]
                elapsed = s['time']
                throughput = s['moves'] / elapsed if elapsed > 0 else 0.0
                print(
                    f"  {mark} ({agents[mark]['name']}): "
                    f"{s['moves']} moves, {elapsed:.3f} s, "
                    f"{throughput:.2f} moves/s, {s['nodes']:,} nodes"
                )
            print("=" * 50)

        return winner, stats

    while True:
        if not any(EMPTY in row for row in board):
            return finish(None)

        move, _, elapsed, nodes = get_move(agents[turn], board, turn, K, rng)

        if trace:
            print(f"\nPly {len(opening) + sum(s['moves'] for s in stats.values()) + 1}")
            print(f"Player to move: {turn}")
            print("Board before move:")
            print_board(board)

        stats[turn]['time'] += elapsed
        stats[turn]['nodes'] += nodes
        stats[turn]['moves'] += 1

        if move is None:
            return finish(None)

        r, c = move
        board[r][c] = turn

        tr = ThreatTracker(board, K, ('X', 'O'), EMPTY)

        if check_win(board, r, c, turn, K):
            return finish(turn)

        turn = OTHER[turn]

def tournament(a, b, num_pairs=10, R=7, C=7, K=4, open_plies=4, seed=0, workers=None):
    rng = random.Random(seed)

    # Draw every random number up front, in the same order as before,
    # so results do not depend on the number of workers.
    jobs = []
    for _ in range(num_pairs):
        opening = random_opening(R, C, open_plies, rng)
        seeds = (rng.getrandbits(64), rng.getrandbits(64))
        jobs.append((a, b, R, C, K, opening, seeds))

    workers = workers or max(1, (os.cpu_count() or 2) - 1)

    agg = {n: {'time': 0.0, 'nodes': 0, 'moves': 0} for n in (a['name'], b['name'])}
    by_color = {'X': [0, 0, 0], 'O': [0, 0, 0]}     # a's W/L/D when playing that color
    pair_scores = []

    with Pool(workers) as pool:
        for i, games in enumerate(pool.imap(_run_pair, jobs), 1):
            pair_total = 0.0
            for a_is_x, winner, stats in games:
                a_mark = 'X' if a_is_x else 'O'
                if winner is None:
                    idx, s = 2, 0.5
                elif winner == a_mark:
                    idx, s = 0, 1.0
                else:
                    idx, s = 1, 0.0
                by_color[a_mark][idx] += 1
                pair_total += s

                names = {'X': a['name'] if a_is_x else b['name'],
                         'O': b['name'] if a_is_x else a['name']}
                for mark in 'XO':
                    for key in ('time', 'nodes', 'moves'):
                        agg[names[mark]][key] += stats[mark][key]

            pair_scores.append(pair_total / 2)
            if i % 10 == 0:
                print(f"  {i}/{num_pairs} pairs done", flush=True)

    n = len(pair_scores)
    mean = sum(pair_scores) / n
    se = statistics.stdev(pair_scores) / math.sqrt(n) if n > 1 else 0.0

    W = sum(v[0] for v in by_color.values())
    L = sum(v[1] for v in by_color.values())
    D = sum(v[2] for v in by_color.values())

    print(f"\n{a['name']} (d{a['depth']}) vs {b['name']} (d{b['depth']}) | "
          f"{R}x{C}, K={K}, {2 * n} games ({n} pairs, {workers} workers)")
    print(f"{a['name']}: {W}W {L}L {D}D -> score {mean:.3f} +/- {2 * se:.3f} (95%, pair-level)")

    print("\nBy color:")
    for mark in 'XO':
        w, l, d = by_color[mark]
        g = w + l + d
        print(f"  {a['name']} as {mark}: {w}W {l}L {d}D  (score {(w + 0.5 * d) / g:.3f})")
    x_wins = by_color['X'][0] + by_color['O'][1]
    print(f"  X (side to move after opening) won {x_wins}/{W + L + D} games")

    print("\nTournament performance:")
    print(f"{'Agent':<18} {'Moves':>8} {'Time (s)':>11} "
          f"{'Moves/s':>11} {'Nodes':>12} {'ms/move':>11}")
    print("-" * 75)
    for name, s in agg.items():
        moves, elapsed = s['moves'], s['time']
        throughput = moves / elapsed if elapsed > 0 else 0.0
        ms_per_move = elapsed * 1000 / moves if moves else 0.0
        print(f"{name:<18} {moves:>8,} {elapsed:>11.3f} "
              f"{throughput:>11.2f} {s['nodes']:>12,} {ms_per_move:>11.2f}")

if __name__ == "__main__":
    new_d4 = {'name': 'ab_v3_d4', 'depth': 4, 'eval': evaluate}
    new_d2 = {'name': 'ab_v3_d2', 'depth': 2, 'eval': evaluate}
    no_force = {'name': 'ab_v3_noforce', 'depth': 4, 'eval': evaluate, 'use_forcing': False}

    tournament(new_d4, new_d2, num_pairs=1, R=9, C=9, K=5, open_plies=2, seed=0, workers=4)