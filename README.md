# CS 152 Final Project: F1 Race Strategy with Hybrid Q-Learning & Minimax

A strategic F1 race simulation combining reinforcement learning (Q-learning) and game-theoretic search (minimax) to optimize pit-stop timing and tyre management decisions.

## Overview

This project models a two-player F1 race as a Markov Decision Process where:
- **MAX (You)**: Uses a hybrid policy combining learned Q-values with minimax lookahead.
- **MIN (Opponent)**: Employs a fixed stationary strategy.
- **State**: Lap count, weather, car conditions (tyre, age, plank wear), cumulative times.
- **Actions**: Stay or pit (choosing soft/medium/hard/inter/wet tyres).

Driver personalities (aggression, smoothness, kerb use, risk tolerance) modulate pace, tyre degradation, and plank wear through multipliers in the Prolog rules engine.

## Project Structure

```
cs152-final-project/
├── prolog/
│   ├── f1_drivers.pl          # Driver roster & trait multipliers
│   ├── f1_rules.pl            # Lap cost, degradation, penalties
│   ├── f1_env.pl              # State transitions, rewards, terminal checks
│   └── f1_minimax.pl          # Minimax search with alpha-beta pruning
├── python/
│   ├── env_bridge.py          # PySWIP bridge to Prolog predicates
│   ├── q_learning.py          # Q-learning trainer (fixed opponent)
│   ├── minimax_runner.py      # Minimax-only race simulator
│   ├── run_race.py            # Hybrid policy executor
│   ├── evaluate.py            # Batch evaluation over drivers/seeds
│   ├── analysis.ipynb         # Jupyter notebook with plots & summary stats
│   └── q_table.pkl            # Learned Q-values (pickled defaultdict)
└── README.md
```

## Key Files

### Prolog Engine (`prolog/`)

- **f1_drivers.pl**: Driver traits (5 drivers: max, lewis, lando, charles, george) and effect tables.
  - Pace bonuses, smoothness multipliers, aggression/kerb use/risk degradation factors.

- **f1_rules.pl**: Track & weather transitions, tyre/setup legality, lap cost computation.
  - Combines base lap time with penalties: drag, degradation, wrong tyre, risk, warmup.
  - Plank wear model (kerb usage + aggression).

- **f1_env.pl**: Game state interface.
  - `state(LapsLeft, Weather, my(...), opp(...))` structure.
  - `legal_actions/3`, `apply_action/4`, `step_reward/4`, `terminal/2`, `evaluate/2`.

- **f1_minimax.pl**: Minimax search (depth-limited, no alpha-beta yet).
  - `minimax_best/4`: Returns best action & value for MAX.
  - `root_values/4`: Debugging utility listing all root actions + values.

### Python Bridge & Learning

- **env_bridge.py**: PySWIP wrapper normalizing Prolog/Python conversions.
  - Methods: `q1()`, `legal_actions()`, `apply_action()`, `step_reward()`, `terminal()`, `minimax_best_player()`.

- **q_learning.py**: Vanilla Q-learning trainer.
  - State aggregation: `(laps_left, weather, my_tyre, my_age_bucket, my_plank_bucket, opp_tyre, opp_age_bucket)`.
  - Fixed opponent always plays `stay`.
  - Saves learned Q-table to `q_table.pkl`.

- **minimax_runner.py**: Pure minimax race simulator.
  - Weather samples stochastically each ply using Prolog transition probabilities.
  - Returns: terminal value, pit counts, step count.

- **run_race.py**: Hybrid policy runner.
  - Consults Q-table; if Q-value exists, uses it with ε-greedy.
  - Otherwise, calls minimax at depth D to generate value estimate.
  - Tracks "overrides" (minimax overrides Q decision) and "consults" (minimax called).

- **evaluate.py**: Batch runner over 30–100 seeds per driver.
  - Aggregates: mean/stdev/min/max utility, DSQ rate, pit stop stats, minimax consultation frequency.

- **analysis.ipynb**: Jupyter notebook.
  - Loads Q-table and runs experiment.
  - Generates 3 plots: utility boxplot, minimax consult/override bar chart, pit stop frequency.
  - Summary table with per-driver statistics.

## Running the Project

### 1. Train Q-Learning

```bash
cd python
python q_learning.py
# Outputs: q_table.pkl
```

Takes ~5–10 minutes (300 episodes × 1000 steps/episode).

### 2. Run Single Hybrid Race

```python
from run_race import run_one_race_hybrid

result = run_one_race_hybrid(
    Q=Q,
    driver="max",
    laps=55,
    start_weather="drizzle",
    regime="unstable",
    depth=4,
    setup=(3, 3, "high"),
    track="interlagos",
    seed=42,
    verbose=True,
)
print(result)
```

### 3. Batch Evaluation

```bash
python evaluate.py
```

Runs 30 races per driver, prints utility stats, DSQ rate, pit stops, minimax metrics.

### 4. Analysis Notebook

```bash
jupyter notebook analysis.ipynb
```

- **Cell 1**: Load Q-table.
- **Cell 2**: Define `run_experiment()` (returns DataFrame).
- **Cell 3**: Run 100 races per driver, collect results.
- **Cell 4**: Summary statistics table.
- **Cells 5–7**: Boxplot, minimax consult bar chart, pit stop bar chart.

## State & Action Representation

### State

```prolog
state(
  LapsLeft,                       % integer, decrements each step
  Weather,                        % dry | drizzle | wet
  my(Tyre, Age, Used, PW, Warm, Time),
  opp(Tyre, Age, Used, PW, Warm, Time)
)
```

- **Tyre**: soft | medium | hard | inter | wet
- **Age**: laps on current tyre (0 = fresh, 1–8 = ok, 9+ = old)
- **Used**: list of tyres already used in race
- **PW**: plank wear (0.0–1.0+; ≥1.0 = illegal DSQ)
- **Warm**: 1 if just pitted (on warmup lap), else 0
- **Time**: cumulative race time in seconds

### Action

```prolog
stay                    % complete another lap on current tyre
pit(soft|medium|hard|inter|wet)  % pit stop + change to new tyre
```

## Q-Learning State Aggregation

Raw state is too large; Q-learning uses a compact key:

```python
(laps_left, weather, my_tyre, my_age_bucket, my_plank_bucket, opp_tyre, opp_age_bucket)
```

Where:
- **age_bucket**: fresh (0), ok (1–8), old (9+)
- **plank_bucket**: safe (≤0.6), warn (≤0.9), critical (≤1.0), illegal (>1.0)

## Hyperparameters

### Q-Learning
- **Episodes**: 300
- **α (learning rate)**: 0.2
- **γ (discount)**: 0.95
- **ε (exploration)**: 0.2

### Race Scenario (default)
- **Laps**: 55
- **Start weather**: drizzle
- **Weather regime**: unstable (higher weather variability)
- **Minimax depth**: 4 (lookahead 4 plies = 2 full rounds)
- **Setup**: (FW=3, RW=3, RH=high)
- **Track**: interlagos

### Terminal Conditions
- Laps exhausted (L ≤ 0)
- Plank wear illegal (PW > 1.0) → DSQ penalty ±1000

## Key Design Decisions

1. **Markov state**: Includes cumulative times so minimax is acyclic.
2. **Driver multipliers**: Applied in lap_cost & plank_wear calculations (MAX only; MIN = neutral).
3. **Weather stochasticity**: Sampled each ply using Prolog transition probabilities.
4. **Reward structure**: From MAX perspective; immediate reward = step_cost(min) - step_cost(max).
5. **Hybrid policy**: Q-table provides fast heuristic; minimax refines at uncertain states.

## Results

Expected output from `evaluate.py`:

```
Driver: max
Utility: mean=...  stdev=...  min=...  max=...
DSQ rate: x/30 = ...%
Avg pits (MAX): ...
Avg pits (MIN): ...
Avg minimax-consults per race: ...
```

See `analysis.ipynb` for plots showing utility distributions and pit strategy by driver.

## Dependencies

- **Python 3.10+**
  - `pyswip` (PySWIP)
  - `pandas`
  - `matplotlib`
  - `jupyter`

- **SWI-Prolog 8.0+**
  - Must be installed and on PATH for PySWIP to locate it.

## Installation

```bash
pip install pyswip pandas matplotlib jupyter
# macOS with Homebrew:
brew install swi-prolog
```

## Future Enhancements

- **Alpha-beta pruning** in minimax for deeper search.
- **More drivers** and tracks.
- **Advanced exploration**: entropy-regularized Q-learning, experience replay.
- **Opponent modeling**: Learn MIN's policy instead of assuming `stay`.
- **GUI visualizer**: Real-time race replay.

## Notes

- Q-learning assumes a fixed opponent (always stays). Real F1 strategies would benefit from opponent modeling.
- Plank wear enforcement is strict; one lap of too-low ride height can trigger DSQ.
- Weather transitions are stochastic; same seed reproduces exact race outcome.

---