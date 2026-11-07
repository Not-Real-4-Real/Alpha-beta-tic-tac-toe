# Tic-Tac-Toe with Alpha-Beta Pruning

A customizable Tic-Tac-Toe engine using **Minimax with Alpha-Beta Pruning**, designed to support different board sizes and win conditions.

## Project Structure

```text
main/
│
├── engine/
│   ├── rules.py
│   └── search_v3.py
│
├── evaluation/
│
├── move_ordering/
│
├── main.py
└── ui.py
```

### Modules

| Component | Description |
|---|---|
| `engine/` | Core game mechanics, board rules, legal move generation, and search algorithms. |
| `evaluation/` | Position evaluation functions used by Minimax to estimate the quality of a board state. |
| `move_ordering/` | Move ordering strategies to improve Alpha-Beta Pruning efficiency. |
| `main.py` | Command-line version of the game, primarily used for debugging and testing. |
| `ui.py` | Main playable version with a graphical user interface. |

## Engine

### `engine/rules.py`

Contains fundamental game constants and board-related utility functions.

**Constants**

- `EMPTY`: Represents an unoccupied cell (`' '`).
- `WIN`: Large score (`10⁹`) representing a winning position.
- `DIRS`: Four directions used to check winning conditions: horizontal, vertical, and both diagonals.
- `nodes_visited`: Counter used to track the number of nodes explored during search.

**Core Functions**

- `check_win(board, r, c, player, K)`: Checks whether the latest move at `(r, c)` creates a winning line of at least *K* consecutive marks. Only four unique directions need to be checked because each direction is explored in both positive and negative orientations.

- `legal_moves(board, radius=2)`: Generates candidate moves from empty cells within a specified neighborhood of existing marks.
  - Returns the center cell when the board is empty.
  - Prioritizes moves closer to the board center.
  - Falls back to all remaining empty cells if no nearby candidates exist.

Localized move generation reduces the branching factor of the search tree, making Minimax and Alpha-Beta Pruning more practical on larger boards.

### `engine/search_v3.py`

Implements the AI's decision-making process using **Minimax with Alpha-Beta Pruning**, enhanced with tactical move detection and incremental threat tracking.

The search algorithm assumes that both players play optimally: the AI attempts to maximize its score, while the opponent attempts to minimize it.

#### 1. Minimax Algorithm

Minimax explores possible future game states by simulating alternating moves between the AI and the opponent.

- **Maximizing player (AI):** Selects the move with the highest evaluation score.
- **Minimizing player (opponent):** Selects the move with the lowest evaluation score.

Each simulated move creates a new search node. The algorithm explores these nodes recursively until it reaches the specified search depth or identifies a tactical outcome.

The evaluation function estimates the quality of the resulting position when the search reaches its depth limit.

#### 2. Alpha-Beta Pruning

Alpha-Beta Pruning improves Minimax by eliminating branches that cannot influence the final decision.

It maintains two bounds throughout the search:

- **Alpha (α):** The best score the maximizing player can guarantee so far (a lower bound).
- **Beta (β):** The best score the minimizing player can guarantee so far (an upper bound).

Whenever `alpha >= beta`, the remaining branches of the current node can be skipped because they cannot produce a better decision for the player making the choice.

This reduces the number of nodes explored without changing the optimal Minimax result, provided the same search depth and candidate moves are used.

Good move ordering can significantly improve pruning efficiency by allowing the algorithm to discover strong moves earlier.

#### 3. Tactical Move Detection

Before expanding a search node, the algorithm checks for immediate winning opportunities and forced defensive moves using `ThreatTracker`.

With `use_forcing=True`, the search applies several tactical rules:

- **Immediate win:** If the current player has an available winning move, return a winning score immediately.
- **Unavoidable fork:** If the previous player has at least two independent winning opportunities, the current player cannot block both, so the search recognizes the forced loss.
- **Forced block:** If the previous player has exactly one immediate winning opportunity, restrict the current player's candidate moves to the cell that blocks it.

Winning scores are adjusted by search depth (`WIN - depth` or `-WIN + depth`) to favor faster victories and delay unavoidable defeats.

These tactical checks allow the search to recognize critical situations without exploring every possible continuation.

#### 4. Incremental Threat Tracking

The search uses `ThreatTracker` from `evaluation/v3.py` to maintain information about potential winning lines.

Instead of recalculating all threats after every simulated move, the tracker is updated incrementally:

- `tr.place(r, c, player)`: Updates the affected winning windows after placing a mark.
- `tr.undo(r, c, player)`: Restores the previous tracker state after the recursive search returns.
- `tr.win_cells(player)`: Identifies cells where the specified player can complete a winning line immediately.

This reduces redundant computation during recursive search.

The board and tracker are always updated together and restored after each simulated move. An optional debug assertion compares the restored tracker against a newly initialized tracker to detect state inconsistencies.

#### 5. `best_move()` — Root-Level Move Selection

The main entry point for the AI search.

```python
best_move(
    board,
    ai,
    human,
    K,
    max_depth=4,
    eval_fn=evaluate,
    use_forcing=True,
    debug=False,
    rng=None
)
```

**Parameters**

| Parameter | Description |
|---|---|
| `board` | Current game board. |
| `ai` | AI player symbol. |
| `human` | Opponent symbol. |
| `K` | Number of consecutive marks required to win. |
| `max_depth` | Maximum search depth. |
| `eval_fn` | Position evaluation function. |
| `use_forcing` | Enables tactical checks and forced moves. |
| `debug` | Prints root candidate scores and selected moves. |
| `rng` | Optional random number generator for tie-breaking. |

**Search procedure**

1. **Initialize search state:** Reset the node counter, create a `ThreatTracker`, and prepare the evaluation weights.

2. **Apply root-level tactical rules:**
   - If the AI has an immediate winning move, consider that move.
   - If the opponent has exactly one immediate winning opportunity, prioritize blocking it.
   - Otherwise, generate candidate moves using `rank_candidates()` from `move_ordering/v3.py`.

3. **Evaluate candidate moves:** Simulate each candidate AI move and recursively call `alphabeta()` to determine its Minimax score. Each root candidate is evaluated independently, with the board and threat tracker restored afterward.

4. **Maintain the best score:** Keep track of the highest Minimax score found so far. This score represents the best outcome the AI can achieve among the candidates examined.

5. **Optimize subsequent searches:** Use the current best score, with a small numerical tolerance, as the alpha lower bound for subsequent root searches. Candidates that cannot improve upon the current best can therefore be pruned earlier.

6. **Resolve ties:** Collect moves whose scores are equal within the defined tolerance (`TOL = 10⁻⁶`). If multiple moves are equally good, randomly select one to introduce variation in the AI's decisions.

**Return values**

```python
best_move, best_score, elapsed_time, nodes_visited
```

- `best_move`: Selected AI move as `(row, column)`.
- `best_score`: Minimax score of the selected move.
- `elapsed_time`: Total search execution time in seconds.
- `nodes_visited`: Number of search nodes explored.

The optional debug mode also prints the highest-scoring root candidates and the moves considered tied for the best score.

The root-level search strategy balances computational efficiency with decision consistency: it uses Alpha-Beta Pruning to eliminate inferior candidates while retaining random selection among moves that are effectively equivalent in Minimax score.

#### 6. Root Alpha Window and Tie Detection

A subtle issue arises when combining Alpha-Beta Pruning with the selection of multiple equally optimal moves.

The root search does not simply need to identify a move with the highest score. It also needs to distinguish genuinely equivalent moves from moves that are actually worse but were cut off before their exact scores could be determined.

**The fail-soft Alpha-Beta window**

The implementation uses fail-soft Alpha-Beta Pruning: instead of clamping its return value to the search window, `alphabeta()` returns the best value encountered during the search.

For a search window `(alpha, beta)`, the returned score has the following interpretation:

| Returned score | Meaning |
|---|---|
| `alpha < v < beta` | Exact minimax value. |
| `v <= alpha` | Upper bound: the true value is at most `v`. |
| `v >= beta` | Lower bound: the true value is at least `v`. |

Consequently, a returned score equal to `alpha` is ambiguous. It may represent an exact score or merely an upper bound.

**Why using `alpha = best_val` can produce false ties**

Consider a root position where the AI has already found a move with a minimax score of 5.

Suppose three candidate moves have the following actual values:

| Move | Actual minimax score | Classification |
|---|---:|---|
| A | 5 | Optimal |
| B | 5 | Equally optimal |
| C | 1 | Inferior |

If subsequent searches use:

```python
alpha = best_val
beta = math.inf
```

the search for B or C can terminate prematurely.

At the minimizing node, suppose the first opponent response produces a score of 5. Since `beta` becomes 5 and `alpha` is already 5, the condition `alpha >= beta` triggers a cutoff.

Both candidates may therefore return 5, even though C has an alternative opponent response that would reduce its actual minimax score to 1.

The root incorrectly interprets this upper-bound result as an exact score and may include an inferior move in the tie-breaking pool.

**The solution: a narrow alpha margin**

To distinguish genuine ties from inferior candidates, the implementation uses:

```python
lo = best_val - 2 * TOL if best_val > -math.inf else -math.inf

val = alphabeta(
    board, 1, max_depth, lo, math.inf, False,
    ai, human, K, (r, c), eval_fn, tr, use_forcing
)
```

Where:

```python
TOL = 1e-6
```

By lowering alpha slightly below the current best score, a genuinely tied candidate can now be searched beyond the equality boundary.

For example, with `best_val = 5`:

- A candidate with an actual score of 5 is strictly inside the search window and can return its exact value.
- A candidate with an actual score of 1 can still trigger a fail-low cutoff and return an upper bound below the window's lower boundary.

The root can then distinguish the two cases rather than treating both as ties.

**Root-level score classification**

After each search, `best_move()` updates its candidate pool using:

```python
if val > best_val + TOL:
    best_val = val
    best_moves = [(r, c)]

elif math.isclose(
    val, best_val,
    rel_tol=0.0,
    abs_tol=TOL
):
    best_moves.append((r, c))
```

The tolerance accounts for small floating-point differences when comparing evaluation scores.

Only candidates that are sufficiently close to the best score are retained. The AI then randomly selects from this pool.

**Why this optimization is useful**

1. **Preserves Alpha-Beta correctness:** The search still uses valid alpha-beta windows. The optimization changes the search window, not the underlying pruning rules.
2. **Avoids false ties:** Inferior candidates that previously returned ambiguous boundary scores are given an opportunity to reveal their actual values.
3. **Maintains pruning efficiency:** The window is only widened by `2 * TOL`, rather than reverting to a full search window for every candidate.
4. **Supports multiple optimal moves:** The AI can introduce variation in its decisions without deliberately sacrificing Minimax quality.

For integer-valued evaluation functions, the equivalent technique is commonly expressed as searching with `alpha = best_val - 1`. This is a narrow-window search that allows equal scores to be distinguished from inferior ones.

The approach is particularly important for this implementation because random tie-breaking is only desirable when the candidate moves are genuinely equivalent in Minimax value.

## Evaluation

The evaluation module estimates the quality of a board position when the Minimax search reaches its depth limit.

A positive score favors the AI, while a negative score favors the opponent. The objective is to provide Minimax with a numerical representation of positional advantage so that it can compare possible future moves.

### 1. Vanilla Evaluation (`evaluation/vanilla.py`)

The initial evaluation function uses a **sliding-window approach** to assess potential winning lines.

For a configurable board size and win condition *K*, it examines every possible sequence of *K* consecutive cells in four directions:

- Horizontal
- Vertical
- Main diagonal
- Anti-diagonal

For each window, it counts the number of AI marks and opponent marks.

**Scoring mechanism**

| Window composition | Score |
|---|---|
| Empty window | 0 |
| AI-only window with *a* marks | +10<sup>a</sup> |
| Opponent-only window with *h* marks | -10<sup>h</sup> |
| Window containing both players | 0 |

The exponential scoring scheme gives greater importance to windows containing more consecutive marks.

For example, with *K* = 5:

| Number of marks | Score |
|---|---:|
| 1 | 10 |
| 2 | 100 |
| 3 | 1,000 |
| 4 | 10,000 |

The opponent's threats receive equivalent negative scores, encouraging the AI to both develop its own winning opportunities and prevent the opponent from doing so.

**Implementation**

The function iterates through every board cell and checks whether a complete window of length *K* can begin there in each of the four directions.

Windows extending beyond the board boundaries are discarded. Windows containing marks from both players are considered blocked and contribute nothing to the evaluation.

The final score is the sum of all valid window scores.

### 2. Limitations of the Vanilla Evaluator

Although the vanilla evaluator provides a simple and intuitive positional heuristic, it has several limitations.

**A. Computational inefficiency**

Every evaluation requires scanning the board and recounting the contents of every possible winning window.

For a board of size (*R* x *C*), the number of candidate windows is bounded by:

```math
O(4RC)
```

Since each window contains *K* cells, the evaluation complexity is:

```math
O(RCK)
```

This computation is repeated across many nodes in the Minimax search tree. As search depth increases, the accumulated evaluation cost becomes significant.

The evaluator also recalculates information about largely unchanged parts of the board after every simulated move.

**B. Limited understanding of threats**

The scoring function considers the number of marks in a window but does not distinguish between different tactical configurations.

For example, two windows containing four AI marks may receive identical scores even if:

- One has both ends blocked or only one available extension.
- The other has two open ends and therefore provides more flexibility.

Similarly, it does not explicitly recognize forks, double threats, or situations where multiple winning opportunities must be defended simultaneously.

As a result, the evaluator can assign similar scores to positions with very different tactical implications.

**C. Lack of positional awareness**

The vanilla evaluator considers winning windows independently.

It does not explicitly account for relationships between nearby windows, shared cells, or how a move can contribute to multiple potential winning lines simultaneously.

It also lacks an explicit representation of spatial relationships, such as the strategic importance of central positions and the proximity of existing marks.

Consequently, it may favor moves with high immediate window scores without adequately considering their broader positional value.

**D. Horizon effect**

Because Minimax searches only up to a fixed depth, the evaluator must estimate positions that may contain unresolved tactical sequences.

A forced win or loss that occurs just beyond the search horizon may not be recognized.

For example, the AI might consider a position favorable based on its current window scores even though the opponent has a forcing sequence that guarantees a win immediately after the search depth.

This is a limitation of depth-limited search combined with heuristic evaluation, rather than a problem exclusive to the vanilla evaluator. More advanced evaluation functions can mitigate the issue, but eliminating it generally requires deeper search or additional tactical extensions.

### 3. Motivation for V3

The limitations of the vanilla evaluator motivated the development of a more structured evaluation system.

Instead of repeatedly scanning the entire board and treating winning windows as independent scoring units, V3 introduces incremental threat tracking and a more detailed representation of positional information.

The main objectives are:

- **Computational efficiency:** Maintain evaluation information incrementally as moves are placed and undone, avoiding unnecessary recalculation.
- **Threat awareness:** Distinguish between different tactical configurations and recognize immediate winning opportunities.
- **Positional evaluation:** Account for relationships between winning windows, shared cells, and the strategic value of potential moves.
- **Search integration:** Provide more informative position scores to Minimax while supporting tactical detection and move ordering.

The vanilla evaluator therefore serves as the baseline for developing a more efficient and strategically informed evaluation system.

## Evaluation V3 — Incremental Threat Tracking

Unlike the vanilla evaluator, which scans the entire board whenever an evaluation is needed, V3 maintains a `ThreatTracker` that incrementally updates information about the board after every move.

The main idea is to **precompute all possible winning windows and maintain their states**, so that placing or removing a stone only requires updating the windows affected by that cell.

### 1. ThreatTracker

A winning window is a sequence of exactly `K` consecutive cells in one of the four directions:

- Horizontal
- Vertical
- Diagonal (`\`)
- Diagonal (`/`)

During initialization, `ThreatTracker` constructs two mappings:

- `window_cells`: Stores the cell indices belonging to every valid winning window.
- `cell_wins`: Maps each board cell to the IDs of all winning windows containing it.

Board coordinates are flattened into a single integer:

```math
\text{index}(r,c)=r \cdot C+c
```

This allows the tracker to use compact integer indices instead of repeatedly storing coordinate pairs.

Each cell belongs to at most 4*K* winning windows, since a window can contain the cell at any of *K* positions in each of the four directions.

The tracker maintains four important data structures:

| Structure | Purpose |
|---|---|
| `cnt[p][w]` | Number of stones belonging to player `p` in window `w`. |
| `esum[w]` | Sum of the flattened indices of empty cells in window `w`. |
| `tally[p][n]` | Number of valid windows containing exactly `n` stones from player `p`, with no opponent stones. |
| `threat[p]` | Maps a winning completion cell to the number of valid *K*-1 windows that can be completed by playing there. |

A window is considered valid for a player if it contains no stones belonging to the opponent.

#### Tracking immediate winning moves

A window containing *K*-1 stones from one player and no opponent stones has exactly one empty cell. That cell is the completion point required to win.

Because `esum[w]` is the sum of all empty-cell indices, it directly identifies this cell when only one empty cell remains.

The `threat` dictionary stores these completion cells. Its keys represent **distinct winning moves**, while its values count how many winning windows each move completes.

This distinction is important:

- Multiple winning windows sharing the same completion cell represent one immediate winning move.
- Multiple distinct completion cells represent multiple immediate winning moves.

Consequently, `len(tr.win_cells(player)) >= 2` identifies a double threat: the player has at least two different winning moves, and the opponent cannot block both with a single move.

### 2. Incremental Updates

The main advantage of `ThreatTracker` is that it does not need to recalculate every window after each move.

When a stone is placed at `(r, c)`, `place()` performs the following operations:

1. Retrieve all winning windows containing the modified cell using `cell_wins`.
2. Remove each affected window's previous contribution from `tally` and `threat`.
3. Update the window's stone count in `cnt`.
4. Update `esum` to account for the newly occupied cell.
5. Add the window's new contribution back to `tally` and `threat`.

The `undo()` method performs the inverse operations, restoring the previous state.

This is particularly useful for Minimax and Alpha-Beta search, where moves are repeatedly placed and undone while exploring different game states.

Instead of rebuilding the entire board representation at every node, the tracker only updates the windows affected by the latest move.

**Complexity:**

- Initialization: *O(RCK)* time and space.
- `place()` / `undo()`: *O(K)* time for fixed four-direction tracking.
- `win_cells()`: *O(1)* to retrieve the dictionary view.
- `windows()`: *O(1)* to retrieve a window count.

The update complexity follows from the fact that each cell belongs to at most 4*K* windows, and each affected window can be updated in constant time.

### 3. Threat Analysis

The tracker provides several methods for examining tactical opportunities.

**`threat_after(tr, r, c, player)`**

Temporarily places a stone, retrieves three measurements, and then restores the tracker:

- Number of distinct immediate winning completion cells.
- Number of valid *K*-1 windows.
- Number of valid *K*-2 windows.

This allows the engine to examine the tactical consequences of a candidate move without permanently modifying the board.

**`hard_rules(tr, board, me, opp)`**

Implements a tactical priority system:

| Condition | Action |
|---|---|
| Current player has an immediate winning move | Play the winning move. |
| Opponent has exactly one immediate winning move | Block it. |
| Opponent has at least two distinct winning moves | Recognize a forced loss. |
| Current player can create at least two distinct winning moves | Recognize a forced-win opportunity. |

These rules prioritize immediate tactical consequences over positional evaluation.

Note that `hard_rules()` is a separate helper in the evaluation module; the current search implementation performs its own immediate-win, forced-block, and double-threat checks.

### 4. Pattern Scoring

V3 uses weighted window counts rather than the vanilla evaluator's simple exponential scoring.

The weights are generated by `make_weights()`:

```math
W[n]=(4K)^{n-1}, \quad 1 \leq n < K
```

For example, when `K = 5`:

| Number of stones | Weight |
|---|---:|
| 1 | 1 |
| 2 | 20 |
| 3 | 400 |
| 4 | 8000 |

The pattern score for a player is:

```math
S_p = \sum_{n=1}^{K-1} W[n] \cdot T_p[n]
```

where T<sub>p</sub>[n] is the number of valid windows containing exactly `n` stones from player `p`, with no opponent stones.

Unlike the vanilla evaluator, which calculates these windows by scanning the board, V3 retrieves their counts directly from `ThreatTracker.tally`.

Overlapping windows are counted independently, allowing a single stone to contribute to multiple potential winning patterns.

### 5. Positional Adjustments

V3 introduces additional factors to make the evaluation more responsive to the current game state.

**Tempo (`TEMPO = 1.5`)**

The score belonging to the player whose turn it is gets multiplied by `TEMPO`.

This gives a slight preference to patterns that the current player can immediately develop.

**Defensive weighting (`DEFEND = 1.1`)**

The opponent's pattern score is multiplied by `DEFEND` before being subtracted.

This makes the evaluator slightly more cautious about allowing the opponent to develop strong patterns.

**Single-threat multiplier**

If the opponent has exactly one immediate winning completion cell, their positional score is doubled.

This emphasizes the urgency of responding to an existing threat.

### 6. Final Evaluation

Before calculating positional scores, `evaluate()` checks for important tactical conditions:

1. If the player whose turn it is has an immediate winning move, return a depth-adjusted winning score.
2. If the opponent has at least two distinct immediate winning moves, return a depth-adjusted losing score.
3. Otherwise, calculate both players' pattern scores and apply the positional adjustments.

The final evaluation is:

```math
E(s) = S_{AI} - DEFEND \cdot S_{human}
```

The values of S<sub>AI</sub> and S<sub>human</sub> may already include the tempo and single-threat adjustments.

Winning and losing scores also account for search depth. The engine prefers faster wins and delays unavoidable losses whenever possible.

### 7. Computational Complexity

After initialization, the pattern evaluation does not need to scan the entire board.

| Operation | Complexity |
|---|---:|
| Initialize `ThreatTracker` | *O(RCK)* |
| Place a stone | *O(K)* |
| Undo a stone | *O(K)* |
| Retrieve immediate winning cells | *O(1)* |
| Retrieve a pattern count | *O(1)* |
| Calculate `pattern_score()` | *O(K)* |
| Calculate `evaluate()` | *O(K)* |

The last two complexities assume the tracker has already been initialized and its state is valid.

The separate `hard_rules()` helper can require *O(RCK)* time in its worst case because it may examine every empty cell and simulate a move.

### 8. Comparison with Vanilla Evaluation

| Aspect | Vanilla | V3 |
|---|---|---|
| Window information | Recalculated on demand | Precomputed and maintained |
| Evaluation | Scans the board | Uses incremental counts |
| Move updates | No persistent tracking | Updates affected windows |
| Immediate threats | Not explicitly represented | Tracked by completion cell |
| Double threats | Not explicitly detected | Explicitly detected |
| Tempo | None | Side-to-move multiplier |
| Defensive weighting | None | Explicit opponent weighting |
| Computational cost per evaluation | *O(RCK)* | *O(K)* |

V3 substantially reduces the cost of evaluating a position and provides explicit information about immediate winning opportunities and double threats. It is therefore a more efficient and tactically informed evaluator, rather than a complete representation of every strategic feature of a Gomoku position.

## Candidate Ranking V2 — Tactical Priorities and Center Preference

Candidate ranking determines the order in which the search algorithm explores possible moves.

This is particularly important for Alpha-Beta Pruning: exploring strong moves earlier increases the likelihood of finding useful alpha-beta bounds and pruning unnecessary branches.

V2 uses a lightweight heuristic based on immediate tactical opportunities and distance from the board center.

### 1. Tactical Priority

For every candidate move, the algorithm temporarily places a stone at that position and checks whether it produces an immediate win for either player.

It evaluates two conditions:

- **AI winning move:** Does placing an AI stone at this position complete a winning sequence?
- **Human winning move:** Would placing a human stone at this position complete a winning sequence?

Based on these checks, each candidate receives one of three priorities:

| Priority | Condition | Meaning |
|---|---|---|
| 2 | `ai_wins` | Immediate winning move for the AI. |
| 1 | `human_wins` | Blocks an immediate winning move for the opponent. |
| 0 | Neither | No immediate win or block is available. |

The AI's immediate winning moves receive the highest priority because winning immediately is preferable to any non-winning move.

Blocking an opponent's immediate win comes next, since failing to block would allow the opponent to win on their next turn.

### 2. Center Preference

For moves with the same tactical priority, V2 prefers positions closer to the center of the board.

The center coordinates are:

```math
r_c=\frac{R-1}{2}, \qquad c_c=\frac{C-1}{2}
```

The Manhattan distance from a candidate position to the center is:

```math
d(r,c)=|r-r_c|+|c-c_c|
```

A smaller distance receives a higher ranking.

The center preference provides a simple positional heuristic: central moves generally have more opportunities to extend in different directions and participate in potential winning sequences.

### 3. Ranking Mechanism

Each candidate is represented by a tuple:

```math
(\text{priority},-\text{distance},(r,c))
```

The list is sorted in descending lexicographical order.

This means:

1. Higher tactical priority comes first.
2. For equal priorities, smaller center distance comes first.
3. If both values are equal, coordinates provide a deterministic tie-break.

The negative distance is used because the list is sorted in descending order.

After sorting, only the move coordinates are returned.

### 4. Computational Complexity

Let *N* be the number of candidate moves.

For each candidate, V2 performs:

- One temporary AI placement and win check.
- One temporary human placement and win check.
- One center-distance calculation.

The win check examines up to four directions, with each direction potentially scanning up to *K*-1 cells on either side of the newly placed stone.

Therefore, candidate analysis takes:

```math
O(NK)
```

Sorting the candidates takes:

```math
O(N\log N)
```

The overall complexity is:

```math
O(NK+N\log N)
```

For fixed *K*, this is effectively *O(N log N)*.

### 5. Characteristics and Limitations

V2 is intentionally inexpensive and easy to understand.

Its main advantages are:

- Prioritizes immediate winning moves.
- Prioritizes blocking immediate opponent wins.
- Uses center preference to establish a reasonable default ordering.
- Requires no additional evaluation weights or persistent data structures.

However, it does not evaluate the strategic quality of non-immediate moves.

For example, it cannot distinguish between:
- A move creating an open three and a move creating a weak pattern.
- A move creating multiple future threats and one creating only a single threat.
- A move that develops an existing formation and an unrelated move equally close to the center.

Consequently, V2 is useful as a basic move-ordering heuristic, but it does not fully exploit the positional information available to the evaluation system.

**Important:** Candidate ranking does not remove moves from the search tree. It only changes their exploration order. Alpha-Beta Pruning remains responsible for deciding which branches can be skipped.

## Candidate Ranking V3 — Cached Neighborhoods and Threat-Based Ordering

V3 aims to reduce the computational cost of candidate ranking by reusing precomputed board information and the tactical information maintained by `ThreatTracker`.

### 1. Precomputed Board Geometry

V3 introduces a global cache, `_TABLES`, keyed by `(R, C, radius)`.

For each board configuration, `_tables()` precomputes three structures:

| Structure | Purpose |
|---|---|
| `order` | All board positions sorted by distance from the center. |
| `pos` | Maps each position to its index in `order`. |
| `nb` | Maps each position to its valid neighboring cells within the specified radius. |

These structures are reused across search nodes, avoiding repeated distance calculations and neighborhood construction.

### 2. Candidate Generation

Instead of examining every empty cell, V3 collects neighboring cells around existing stones.

- Each occupied cell contributes its precomputed neighborhood.
- A set removes duplicate positions.
- Occupied cells are filtered out.
- Remaining candidates are sorted using the cached center-first ordering.

For an empty board, the center position is returned immediately. If no candidates are generated, the algorithm falls back to all remaining empty cells.

This approach focuses the search on positions near existing formations, reducing the branching factor.

### 3. Threat-Based Prioritization

V3 reuses `ThreatTracker` to retrieve immediate winning completion cells for both players.

These positions are placed at the beginning of the candidate list:

1. AI immediate winning moves.
2. Opponent immediate winning moves that need to be blocked.
3. Remaining candidates, ordered by distance from the center.

Unlike V2, V3 does not temporarily place both players' stones at every candidate and call `check_win()`. It obtains this tactical information directly from the tracker's incrementally maintained threat data.

Note that winning and blocking moves share the same priority category internally; AI winning moves appear first because they are concatenated before opponent threats.

### 4. Computational Complexity

Let:
- \(N\) be the number of occupied cells.
- \(M\) be the number of generated candidates.
- \(q=(2r+1)^2-1\) be the maximum neighborhood size for radius \(r\).

After precomputation:

- Neighborhood collection: \(O(Nq)\).
- Candidate filtering and sorting: \(O(M\log M)\).
- Threat retrieval and combination: \(O(H+M)\), where \(H\) is the number of distinct hot moves.

Therefore:

\[
O(Nq+M\log M+H)
\]

For a fixed radius, this simplifies to:

\[
\boxed{O(N+M\log M+H)}
\]

The initial cache construction is performed only once per board configuration and radius.

### 5. Comparison with V2

| Aspect | V2 | V3 |
|---|---|---|
| Candidate generation | Receives candidates externally | Uses occupied-cell neighborhoods |
| Win/block detection | Simulates moves and calls `check_win()` | Reuses `ThreatTracker` |
| Center ordering | Calculates distance per candidate | Uses cached ordering |
| Duplicate removal | Depends on input | Uses a set |
| Main objective | Simple tactical ordering | Reduce repeated computation |

V3 improves efficiency by combining cached spatial information with incremental threat tracking. Its main limitation is that a fixed neighborhood radius can exclude strategically relevant moves far from existing stones.
