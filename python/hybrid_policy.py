from q_learning import parse_state_key


def greedy_q_action(Q, state_key, legal_actions):
    """
    Select the greedy action (highest Q-value) from legal actions.
    Arguments
    - Q: dict-like mapping (state_key, action_str) -> float
    - state_key: hashable state representation (tuple)
    - legal_actions: list[str] of valid actions in this state
    Outputs
    - best_action: str
    - best_q_value: float
    """

    if not legal_actions:
        return "stay", 0.0

    best_a = legal_actions[0]
    best_q = Q[(state_key, best_a)]

    for a in legal_actions[1:]:
        qa = Q[(state_key, a)]
        if qa > best_q:
            best_q = qa
            best_a = a
    return best_a, best_q


def triggers_fire(state_key, prev_weather):
    """
    Decide whether to consult minimax this lap, and return a trigger dictionary.

    Arguments
    - state_key: tuple returned by parse_state_key(...). Must have:
        index 0 = laps_left (int)
        index 1 = current weather (str)
        index -1 = plank bucket (str)  (assumes plank bucket is last)
      It can contain additional fields in the middle (opponent tyre, etc).
    - prev_weather: weather at the start of the previous lap (str) or None

    Outputs
    - fired: bool, True if any trigger fired
    - trig: dict with keys:
        pit_window: bool
        weather_transition: bool
        dsq_risk: bool
    """
    laps_left = state_key[0]
    curr_weather = state_key[1]
    my_plank_bucket = state_key[-1]

    pit_window = (laps_left <= 10)
    weather_transition = (prev_weather is not None and curr_weather != prev_weather)
    dsq_risk = (my_plank_bucket in ("critical", "illegal"))

    trig = {
        "pit_window": pit_window,
        "weather_transition": weather_transition,
        "dsq_risk": dsq_risk,
    }
    fired = pit_window or weather_transition or dsq_risk
    return fired, trig


def choose_action_hybrid(B, Q, state_str, prev_weather, depth=4, margin=5.0):
    """
    Hybrid policy for MAX (Q-learning default + minimax on triggers).
    Behavior
    - Compute greedy Q-learning action.
    - If no trigger fires, return Q action.
    - If a trigger fires, consult minimax root values and override only if
      minimax is better than Q by at least `margin`.

    Arguments
    - B: EnvBridge instance (PySWIP bridge into Prolog)
    - Q: dict-like mapping (state_key, action_str) -> float
    - state_str: Prolog state term as a string, e.g. "state(...)"
    - prev_weather: str or None, weather at the start of the previous lap
    - depth: int, minimax search depth (plies)
    - margin: float, required advantage for minimax to override

    Outputs
    - action_str: str, chosen action ("stay" or "pit(x)")
    - info: dict with keys:
        used: "q" or "minimax"
        q_action: str
        q_value: float
        trigger: dict
        consulted_minimax: bool
        override: bool
        minimax_action: str or None
        minimax_value: float or None
        minimax_q_value: float or None
    """

    sk = parse_state_key(state_str)
    legal = B.legal_actions(state_str, "max")
    a_q, q_val = greedy_q_action(Q, sk, legal)
    fired, trig = triggers_fire(sk, prev_weather)

    info = {
        "used": "q",
        "q_action": a_q,
        "q_value": q_val,
        "trigger": trig,
        "consulted_minimax": False,
        "override": False,
        "minimax_action": None,
        "minimax_value": None,
        "minimax_q_value": None,
    }

    if not fired:
        return a_q, info

    pairs = B.root_values(state_str, depth, "max")
    info["consulted_minimax"] = True
    if not pairs:
        return a_q, info

    mm_action, mm_val = max(pairs, key=lambda x: x[1])
    mm_map = {a: v for a, v in pairs}
    mm_q_val = mm_map.get(a_q)

    info["minimax_action"] = mm_action
    info["minimax_value"] = mm_val
    info["minimax_q_value"] = mm_q_val
    compare_q = mm_q_val if mm_q_val is not None else q_val

    if mm_val >= compare_q + margin:
        info["used"] = "minimax"
        info["override"] = True
        return mm_action, info
    return a_q, info