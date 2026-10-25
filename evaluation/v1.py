from engine.rules import *

def evaluate(board, ai, human, K):
    "Vanilla version."
    R, C = len(board), len(board[0])
    score = 0

    for r in range(R):
        for c in range(C):
            for dr, dc in DIRS:
                er = r + (K - 1) * dr
                ec = c + (K - 1) * dc

                if not (0 <= er < R and 0 <= ec < C):
                    continue

                a = h = 0
                for k in range(K):
                    v = board[r + k * dr][c + k * dc]

                    if v == ai:
                        a += 1
                    elif v == human:
                        h += 1

                if a and h:
                    continue                # blocked window, worthless
                if a:
                    score += 10 ** a
                elif h:
                    score -= 10 ** h

    return score