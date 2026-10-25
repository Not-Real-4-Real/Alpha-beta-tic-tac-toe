import math
import time

from engine.rules import *

from evaluation.v1 import evaluate

from move_ordering.v2 import rank_candidates

def alphabeta(board, depth, max_depth, alpha, beta, maximizing, ai, human, K, last):
    global nodes_visited
    nodes_visited += 1

    r, c = last
    mover = human if maximizing else ai      # the player who just moved

    if check_win(board, r, c, mover, K):
        return WIN - depth if mover == ai else depth - WIN

    if depth >= max_depth:
        return evaluate(board, ai, human, K)

    moves = rank_candidates(board, legal_moves(board), ai, human, K)
    
    if not moves:
        return 0                              # board full: draw

    if maximizing:
        value = -math.inf
        for (mr, mc) in moves:
            board[mr][mc] = ai
            value = max(value, alphabeta(board, depth + 1, max_depth, alpha, beta,
                                         False, ai, human, K, (mr, mc)))
            board[mr][mc] = EMPTY

            alpha = max(alpha, value)
            if alpha >= beta:
                break

        return value
    
    else:
        value = math.inf
        for (mr, mc) in moves:
            board[mr][mc] = human
            value = min(value, alphabeta(board, depth + 1, max_depth, alpha, beta,
                                         True, ai, human, K, (mr, mc)))
            board[mr][mc] = EMPTY
            
            beta = min(beta, value)
            if alpha >= beta:
                break

        return value

def best_move(board, ai, human, K, max_depth=4):
    global nodes_visited
    nodes_visited = 0
    best, best_val = None, -math.inf
    alpha, beta = -math.inf, math.inf

    start = time.perf_counter()

    moves = rank_candidates(board, legal_moves(board), ai, human, K)

    for (r, c) in moves:
        board[r][c] = ai
        val = alphabeta(board, 1, max_depth, alpha, beta, False, ai, human, K, (r, c))
        board[r][c] = EMPTY

        if val > best_val:
            best_val, best = val, (r, c)
        alpha = max(alpha, best_val)

    elapsed = time.perf_counter() - start
        
    return best, best_val, elapsed, nodes_visited