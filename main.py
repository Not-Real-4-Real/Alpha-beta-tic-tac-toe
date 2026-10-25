import math
import time

from engine.rules import *
from engine.search import best_move

def simulate_games(
    num_games=100,
    R=3,
    C=3,
    K=3,
    x_depth=4,
    o_depth=4,
    progress_interval=10
):
    """
    Simulate AI vs AI games using alpha-beta search.
    X and O use independent search depths.
    The starting player alternates between games.
    """
    if num_games < 1:
        raise ValueError("num_games must be at least 1.")
    if x_depth < 1 or o_depth < 1:
        raise ValueError("Search depths must be at least 1.")
    if R < 1 or C < 1 or not (1 <= K <= max(R, C)):
        raise ValueError("Invalid board dimensions or K.")

    total_wins = {'X': 0, 'O': 0}
    draws = 0
    starter_wins = {'X': 0, 'O': 0}
    starter_losses = {'X': 0, 'O': 0}

    search_time = {'X': 0.0, 'O': 0.0}
    nodes_visited_by_player = {'X': 0, 'O': 0}
    moves_by_player = {'X': 0, 'O': 0}

    depths = {'X': x_depth, 'O': o_depth}
    other = {'X': 'O', 'O': 'X'}

    simulation_start = time.perf_counter()

    for game in range(num_games):
        board = [[EMPTY] * C for _ in range(R)]

        starter = 'X' if game % 2 == 0 else 'O'
        turn = starter

        while True:
            move, score, elapsed, nodes = best_move(
                board,
                ai=turn,
                human=other[turn],
                K=K,
                max_depth=depths[turn]
            )

            search_time[turn] += elapsed
            nodes_visited_by_player[turn] += nodes
            moves_by_player[turn] += 1

            if move is None:
                draws += 1
                break

            r, c = move
            board[r][c] = turn

            if check_win(board, r, c, turn, K):
                total_wins[turn] += 1

                if turn == starter:
                    starter_wins[starter] += 1
                else:
                    starter_losses[starter] += 1

                break

            # Full board: draw.
            if not any(EMPTY in row for row in board):
                draws += 1
                break

            turn = other[turn]

        completed = game + 1

        if progress_interval > 0 and completed % progress_interval == 0:
            print(
                f"Games: {completed:,}/{num_games:,} | "
                f"X wins: {total_wins['X']:,} | "
                f"O wins: {total_wins['O']:,} | "
                f"Draws: {draws:,}"
            )

    total_elapsed = time.perf_counter() - simulation_start
    total_moves = sum(moves_by_player.values())
    total_nodes = sum(nodes_visited_by_player.values())
    total_search_time = sum(search_time.values())

    print("\n========== SIMULATION RESULTS ==========")
    print(f"Games played:       {num_games:,}")
    print(f"Board:              {R} x {C}")
    print(f"Winning length K:   {K}")
    print(f"X search depth:     {x_depth}")
    print(f"O search depth:     {o_depth}")
    print(f"X wins:             {total_wins['X']:,}")
    print(f"O wins:             {total_wins['O']:,}")
    print(f"Draws:              {draws:,}")

    print("\nWin rates:")
    print(f"X:                  {100 * total_wins['X'] / num_games:.2f}%")
    print(f"O:                  {100 * total_wins['O'] / num_games:.2f}%")
    print(f"Draw:               {100 * draws / num_games:.2f}%")

    print("\nResults by starting player:")
    for player in ('X', 'O'):
        games_started = sum(
            1 for game in range(num_games)
            if ('X' if game % 2 == 0 else 'O') == player
        )
        player_draws = (
            games_started
            - starter_wins[player]
            - starter_losses[player]
        )

        print(
            f"{player} started: "
            f"{starter_wins[player]} wins, "
            f"{starter_losses[player]} losses, "
            f"{player_draws} draws"
        )

    print("\nSearch statistics by player:")
    for player in ('X', 'O'):
        moves = moves_by_player[player]
        nodes = nodes_visited_by_player[player]
        elapsed = search_time[player]

        print(f"\n{player} (depth {depths[player]}):")
        print(f"  Moves searched:   {moves:,}")
        print(f"  Nodes visited:    {nodes:,}")
        print(f"  Average nodes/move: {nodes / moves:,.2f}"
              if moves else "  Average nodes/move: N/A")
        print(f"  Search time:      {elapsed:.2f} seconds")
        print(f"  Average time/move: {elapsed / moves:.4f} seconds"
              if moves else "  Average time/move: N/A")

    print("\nOverall performance:")
    print(f"Total moves searched: {total_moves:,}")
    print(f"Total nodes visited:  {total_nodes:,}")
    print(f"Total search time:    {total_search_time:.2f} seconds")
    print(f"Total elapsed time:   {total_elapsed:.2f} seconds")
    print(f"Games per second:     {num_games / total_elapsed:.2f}"
          if total_elapsed else "Games per second:     N/A")

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
            move, score, elapsed, nodes = best_move(board, ai, human, K, max_depth)

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
    play()
    
    # simulate_games(
    #     num_games=10,
    #     R=7,
    #     C=7,
    #     K=4,
    #     x_depth=3,
    #     o_depth=4,
    #     progress_interval=1
    # )