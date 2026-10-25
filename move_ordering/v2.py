from engine.rules import *

def rank_candidates(board, candidates, ai, human, K):
    """
    Cheap move ordering:
    1. Immediate AI wins
    2. Cells that block an immediate human win
    3. Remaining moves, center-first
    """
    R, C = len(board), len(board[0])
    center_r, center_c = (R - 1) / 2, (C - 1) / 2

    ranked = []

    for r, c in candidates:
        # Does AI win by playing here?
        board[r][c] = ai
        ai_wins = check_win(board, r, c, ai, K)
        board[r][c] = EMPTY

        # Would the human win by playing here?
        board[r][c] = human
        human_wins = check_win(board, r, c, human, K)
        board[r][c] = EMPTY

        if ai_wins:
            priority = 2
        elif human_wins:
            priority = 1
        else:
            priority = 0

        distance = (
            abs(r - center_r) + abs(c - center_c)
        )

        ranked.append((priority, -distance, (r, c)))

    ranked.sort(reverse=True)

    return [move for _, _, move in ranked]