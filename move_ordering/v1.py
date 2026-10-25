from engine.rules import *

from evaluation.v1 import evaluate

def rank_candidates(board, candidates, ai, human, K):
    """
    Heavy ranking:
      3: Immediate AI win
      2: Blocks an immediate human win
      1: Ordinary positional move
    """
    ranked = []

    for r, c in candidates:
        # Test the AI's hypothetical move.
        board[r][c] = ai
        ai_wins = check_win(board, r, c, ai, K)
        ai_score = evaluate(board, ai, human, K)
        board[r][c] = EMPTY

        # Test the human's hypothetical move at the same cell.
        board[r][c] = human
        human_wins = check_win(board, r, c, human, K)
        human_score = evaluate(board, ai, human, K)
        board[r][c] = EMPTY

        # Tactical priority dominates heuristic score.
        if ai_wins:
            priority = 3
        elif human_wins:
            priority = 2
        else:
            priority = 1

        score = ai_score - human_score

        ranked.append((priority, score, (r, c)))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)

    return [move for _, _, move in ranked]