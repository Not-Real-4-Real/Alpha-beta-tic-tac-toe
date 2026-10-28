import random, time, math, statistics

from engine.rules import *
from engine.search import *

from evaluation.v1 import evaluate as evaluate_v1
from evaluation.v2 import evaluate as evaluate_v2

OTHER = {'X': 'O', 'O': 'X'}

def random_opening(R, C, plies, rng):
    """Random cells, alternating X/O. Keep plies <= 2*(K-1) so no one can win."""
    cells = rng.sample([(r, c) for r in range(R) for c in range(C)], plies)
    return cells

def play_game(R, C, K, x_agent, o_agent, opening, verbose=False):
    board = [[EMPTY] * C for _ in range(R)]
    agents = {'X': x_agent, 'O': o_agent}
    stats = {
        p: {'time': 0.0, 'nodes': 0, 'moves': 0}
        for p in 'XO'
    }

    turn = 'X'

    # Apply the opening moves.
    for r, c in opening:
        board[r][c] = turn
        turn = OTHER[turn]

    # Display the initial board, including the opening.
    if verbose:
        print("\n" + "=" * 50)
        print(f"Game: X={x_agent['name']} vs O={o_agent['name']}")
        print(f"Opening moves: {len(opening)}")
        print("Initial board:")
        print_board(board)

    def finish(winner):
        if verbose:
            total_moves = len(opening) + sum(
                s['moves'] for s in stats.values()
            )
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
                    f"{s['moves']} moves, "
                    f"{elapsed:.3f} s, "
                    f"{throughput:.2f} moves/s, "
                    f"{s['nodes']:,} nodes"
                )

            print("=" * 50)

        return winner, stats

    while True:
        if not any(EMPTY in row for row in board):
            return finish(None)

        agent = agents[turn]

        move, _, elapsed, nodes = best_move(
            board,
            ai=turn,
            human=OTHER[turn],
            K=K,
            max_depth=agent['depth'],
            eval_fn=agent['eval']
        )

        stats[turn]['time'] += elapsed
        stats[turn]['nodes'] += nodes
        stats[turn]['moves'] += 1

        if move is None:
            return finish(None)

        r, c = move
        board[r][c] = turn

        if check_win(board, r, c, turn, K):
            return finish(turn)

        turn = OTHER[turn]

def tournament(a, b, num_pairs=10, R=7, C=7, K=4, open_plies=4, seed=0, verbose=False):
    """
    Each random opening is played twice, with colors swapped.
    verbose=True prints the initial and final board of every game.
    """
    rng = random.Random(seed)

    scores = []
    agg = {
        n: {'time': 0.0, 'nodes': 0, 'moves': 0}
        for n in (a['name'], b['name'])
    }

    W = L = D = 0

    for pair_idx in range(num_pairs):
        opening = random_opening(R, C, open_plies, rng)

        for a_is_x in (True, False):
            x, o = (a, b) if a_is_x else (b, a)

            winner, stats = play_game(
                R, C, K, x, o, opening,
                verbose=verbose
            )

            a_mark = 'X' if a_is_x else 'O'

            # Aggregate by agent, not by mark.
            for mark, agent in (('X', x), ('O', o)):
                for key in ('time', 'nodes', 'moves'):
                    agg[agent['name']][key] += stats[mark][key]

            if winner is None:
                D += 1
                scores.append(0.5)
            elif winner == a_mark:
                W += 1
                scores.append(1.0)
            else:
                L += 1
                scores.append(0.0)

    n = len(scores)
    mean = sum(scores) / n
    se = statistics.stdev(scores) / math.sqrt(n) if n > 1 else 0.0

    print(
        f"\n{a['name']} (d{a['depth']}) vs "
        f"{b['name']} (d{b['depth']}) | "
        f"{R}x{C}, K={K}, {n} games"
    )
    print(
        f"{a['name']}: {W}W {L}L {D}D "
        f"-> score {mean:.3f} +/- {2 * se:.3f} (95%)"
    )

    print("\nTournament performance:")
    print(
        f"{'Agent':<18} {'Moves':>8} {'Time (s)':>11} "
        f"{'Moves/s':>11} {'Nodes':>12} {'ms/move':>11}"
    )
    print("-" * 75)

    for name, s in agg.items():
        moves = s['moves']
        elapsed = s['time']

        throughput = moves / elapsed if elapsed > 0 else 0.0
        ms_per_move = elapsed * 1000 / moves if moves else 0.0

        print(
            f"{name:<18} {moves:>8,} {elapsed:>11.3f} "
            f"{throughput:>11.2f} {s['nodes']:>12,} "
            f"{ms_per_move:>11.2f}"
        )

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

def play():
    human, ai = 'X', 'O'

    print("Dynamic Tic tac toe")
    print("Enter the board dimensions and winning length.")

    try:
        R = int(input("Rows: "))
        C = int(input("Columns: "))
        K = int(input("Consecutive marks to win (K): "))
        max_depth = int(input("Search depth (default 4): ") or "4")
    except ValueError:
        print("Please enter valid integers.")
        return

    if R < 1 or C < 1 or not (1 <= K <= max(R, C)):
        print("Invalid dimensions or K.")
        return

    if max_depth < 1:
        print("Search depth must be at least 1.")
        return

    board = [[EMPTY] * C for _ in range(R)]
    turn = ai  # Human goes first.

    while True:
        print_board(board)

        if turn == human:
            try:
                raw = input(
                    f"Your move (row col, 1-{R} and 1-{C}): "
                )
                parts = raw.split()

                if len(parts) != 2:
                    print("Enter two integers: row col.")
                    continue

                r, c = int(parts[0]) - 1, int(parts[1]) - 1

            except ValueError:
                print("Enter valid integers.")
                continue

            if not (0 <= r < R and 0 <= c < C):
                print("Move is outside the board.")
                continue

            if board[r][c] != EMPTY:
                print("That cell is occupied.")
                continue

            board[r][c] = human

            if check_win(board, r, c, human, K):
                print_board(board)
                print("Human (X) wins!")
                break

            turn = ai

        else:
            move, score, elapsed, nodes = best_move(board, ai, human, K, max_depth, evaluate_v1)

            if move is None:
                print("Draw!")
                break

            r, c = move
            board[r][c] = ai

            print(f"AI plays row {r + 1}, column {c + 1}")
            print(f"Evaluation score: {score}")
            print(f"Search time: {elapsed:.4f} seconds")
            print(f"Nodes visited: {nodes:,}")

            if elapsed > 0:
                print(f"Search throughput: {nodes / elapsed:,.0f} nodes/s")

            if check_win(board, r, c, ai, K):
                print_board(board)
                print("AI (O) wins!")
                break

            turn = human

        if not legal_moves(board):
            print_board(board)
            print("Draw!")
            break

if __name__ == "__main__":
    # play()

    v1 = {'name': 'vanilla', 'eval': evaluate_v1, 'depth': 3}
    v2 = {'name': 'v2',      'eval': evaluate_v2, 'depth': 3}

    tournament(
        v1,
        v2,
        num_pairs=10,
        R=7,
        C=7,
        K=4,
        open_plies=4,
        seed=0,
        verbose=True
    )