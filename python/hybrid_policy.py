from q_learning import parse_state_key


def greedy_q_action(Q, state_key, legal_actions):
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


def triggers_fire(state_key, prev_weather: str | None) -> tuple[bool, dict]:
    laps_left, weather, _, my_age_bucket, my_plank_bucket = state_key

    pit_window = (my_age_bucket == "old") or (laps_left <= 3)
    weather_transition = (prev_weather is not None) and (weather != prev_weather)
    dsq_risk = my_plank_bucket in ("warn", "critical")

    fired = pit_window or weather_transition or dsq_risk
    details = {
        "pit_window": pit_window,
        "weather_transition": weather_transition,
        "dsq_risk": dsq_risk,
    }
    return fired, details


def choose_action_hybrid(B, Q, state_str: str, prev_weather: str | None, depth: int = 4, margin: float = 5.0):
    """
    Hybrid policy:
      - default: greedy Q action
      - if triggers fire: consult minimax root values, override if clearly better

    Returns:
      action_str, info_dict
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
        "override": False,
        "minimax_action": None,
        "minimax_value": None,
    }

    if not fired:
        return a_q, info

    # consult minimax only on trigger
    pairs = B.root_values(state_str, depth, "max")
    if not pairs:
        return a_q, info  # fallback

    # best minimax action at root
    mm_action, mm_val = max(pairs, key=lambda x: x[1])

    # find minimax value for the Q-chosen action if present
    mm_map = {a: v for a, v in pairs}
    mm_q_val = mm_map.get(a_q, None)

    info["minimax_action"] = mm_action
    info["minimax_value"] = mm_val

    # override rule:
    # - if Q action not in minimax list, or
    # - if minimax beats Q by margin (use minimax’s own values for comparison)
    compare_q = mm_q_val if mm_q_val is not None else q_val
    if mm_val >= compare_q + margin:
        info["used"] = "minimax"
        info["override"] = True
        return mm_action, info

    return a_q, info