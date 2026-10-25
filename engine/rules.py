EMPTY = ' '
WIN = 10**9
nodes_visited = 0
DIRS = ((0, 1), (1, 0), (1, 1), (1, -1))

def check_win(board, r, c, player, K):
    R, C = len(board), len(board[0])

    for dr, dc in DIRS:
        count = 1
        
        for sign in (1, -1):
            i = r + sign * dr
            j = c + sign * dc
            
            while 0 <= i < R and 0 <= j < C and board[i][j] == player:
                count += 1
                i += sign * dr
                j += sign * dc
        
        if count >= K:
            return True
    
    return False

def legal_moves(board, radius=2):
    "Empty cells near existing marks, center-first."
    R, C = len(board), len(board[0])
    occupied = [(r, c) for r in range(R) for c in range(C) if board[r][c] != EMPTY]

    if not occupied:
        return [(R // 2, C // 2)]
    
    cand = set()
    for r, c in occupied:
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                i = r + dr
                j = c + dc

                if 0 <= i < R and 0 <= j < C and board[i][j] == EMPTY:
                    cand.add((i, j))

    if not cand:  # rare: every empty cell is far from all marks
        cand = {(r, c) for r in range(R) for c in range(C) if board[r][c] == EMPTY}

    return sorted(cand, key=lambda m: abs(m[0] - R // 2) + abs(m[1] - C // 2))