from engine.rules import *

PATTERN_WEIGHTS = {
    "open_four":        100000,
    "closed_four":      20000,
    "open_three":       1000,
    "broken_three":     500,
    "closed_three":     200,
    "open_two":         50,
    "closed_two":       10,
    "single":           1,
}

def extract_lines(board, K):
    R, C = len(board), len(board[0])
    lines = []

    for r in range(R):
        for c in range(C):
            for dr, dc in DIRS:
                # Only begin at the start of a line.
                pr, pc = r - dr, c - dc

                if 0 <= pr < R and 0 <= pc < C:
                    continue

                line = []
                i, j = r, c

                while 0 <= i < R and 0 <= j < C:
                    line.append(board[i][j])
                    i += dr
                    j += dc

                if len(line) >= K:
                    lines.append(line)

    return lines

def remove_subsets(threats):
    """
    Remove any threat whose stone positions are a strict
    subset of another threat in the same line.
    """
    unique = {frozenset(stones): kind for stones, kind in threats}
    unique_sets = set(unique.keys())

    return [
            (tuple(s), unique[s])
            for s in unique_sets
            if not any(s < other for other in unique_sets)
        ]

def score_line(line, player, K,  weights=PATTERN_WEIGHTS):
    n = len(line)

    patterns = {}

    for start in range(n - K + 1):
        cells = line[start:start + K]

        # A pattern cannot extend through an opponent's stone.
        if any(v != EMPTY and v != player for v in cells):
            continue

        stones = tuple(
            start + i
            for i, v in enumerate(cells)
            if v == player
        )

        count = len(stones)

        if count == 0:
            continue

        pattern = patterns.setdefault(stones, {
            "count": count,
            "winning_cells": set(),
        })

        # A K-1 pattern has one empty cell that completes a win.
        if count == K - 1:
            for i, v in enumerate(cells):
                if v == EMPTY:
                    pattern["winning_cells"].add(start + i)

    threats = []

    for stones, pattern in patterns.items():
        count = pattern["count"]

        first = stones[0]
        last = stones[-1]

        if first > 0 and line[first - 1] == player:
            continue
        if last + 1 < n and line[last + 1] == player:
            continue

        # Number of contiguous groups of our stones.
        runs = 1 + sum(
            stones[i] > stones[i - 1] + 1
            for i in range(1, count)
        )

        open_ends = sum((
            first > 0 and line[first - 1] == EMPTY,
            last + 1 < n and line[last + 1] == EMPTY,
        ))

        if count == K - 1:
            winning_cells = pattern["winning_cells"]

            if len(winning_cells) >= 2:
                kind = "open_four"
            else:
                kind = "closed_four"

        elif count == K - 2:
            if runs > 1:
                kind = "broken_three" if open_ends == 2 else "closed_three"
            elif open_ends == 2:
                kind = "open_three"
            else:
                kind = "closed_three"

        elif count == 2:
            kind = "open_two" if open_ends == 2 else "closed_two"

        elif count == 1:
            kind = "single"

        else:
            # Other counts can be added to the pattern catalog later.
            continue

        threats.append((stones, kind))

    threats = remove_subsets(threats)

    return sum(weights[kind] for _, kind in threats)

def evaluate(board, ai, human, K):
    score = 0

    for line in extract_lines(board, K):
        score += score_line(line, ai, K)
        score -= score_line(line, human, K)

    return score