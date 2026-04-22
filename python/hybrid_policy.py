# python/hybrid_policy.py
from q_learning import parse_state_key


def greedy_q_action(Q, state_key, legal_actions):
    """
    Select the greedy action (highest Q-value) from the legal actions.

    Arguments:
      Q: dict-like mapping (state_key, action_str) -> float
      state_key: tuple produced by parse_state_key(state_str)
      legal_actions: list of action strings, e.g. ["stay","pit(medium)",...]

    Returns:
      best_action: str
      best_q_value: float
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
def triggers_fire(state_key, prev_weather, prev_opp_action):
    """
    Decide whether to consult minimax this lap (event-based triggers).

    Design goals:
    1) Don't consult minimax every lap.
    2) Consult when the decision is actually hard/important:
       - tyres are old (pit pressure)
       - weather just changed into a risky regime
       - plank is near-illegal
       - opponent just pitted (tactical response)
       - you are on the wrong tyre AND it's newly risky (mismatch onset)

    Arguments:
      state_key: tuple from parse_state_key, expected to contain at least:
        index 0: laps_left (int)
        index 1: current weather (str)
        index 2: my_tyre (str)
        index 3: my_age_bucket (str: "fresh"|"ok"|"old")
        index 4: my_plank_bucket (str: "safe"|"warn"|"critical"|"illegal")
        optionally more fields after that (opp tyre/age etc.)

      prev_weather: weather at the START of previous lap (str) or None
      prev_opp_action: opponent action from previous lap (str) or None

    Returns:
      fired: bool
      trig: dict[str,bool] with keys:
        pit_window: tyres are old (pit pressure)
        weather_transition: weather got worse (dry->drizzle or drizzle->wet)
        dsq_risk: plank in critical/illegal bucket
        opp_pitted: opponent pitted last lap
        mismatch_onset: tyre/weather mismatch became newly relevant this lap
    """
    laps_left = state_key[0]
    curr_weather = state_key[1]
    my_tyre = state_key[2]
    my_age_bucket = state_key[3]
    my_plank_bucket = state_key[4]

    # 1) Pit pressure: only consult when tyres are actually "old"
    pit_window = (my_age_bucket == "old")

    # 2) Weather transition: only consult when it gets WORSE, not any change.
    # (dry->drizzle, drizzle->wet are the big decision moments)
    weather_transition = False
    if prev_weather is not None:
        got_worse = (
            (prev_weather == "dry" and curr_weather in ("drizzle", "wet")) or
            (prev_weather == "drizzle" and curr_weather == "wet")
        )
        weather_transition = got_worse

    # 3) DSQ risk: plank is near illegal
    dsq_risk = (my_plank_bucket in ("critical", "illegal"))

    # 4) Opponent pitted last lap: tactical response moment
    opp_pitted = bool(prev_opp_action) and prev_opp_action.startswith("pit(")

    # 5) Tyre/weather mismatch onset:
    # Fire only if mismatch is TRUE now AND weather just worsened,
    # so it doesn't spam every lap you remain mismatched.
    is_slick = my_tyre in ("soft", "medium", "hard")
    mismatch_now = is_slick and (curr_weather in ("drizzle", "wet"))
    mismatch_onset = mismatch_now and weather_transition

    trig = {
        "pit_window": pit_window,
        "weather_transition": weather_transition,
        "dsq_risk": dsq_risk,
        "opp_pitted": opp_pitted,
        "mismatch_onset": mismatch_onset,
    }

    fired = any(trig.values())
    return fired, trig


def choose_action_hybrid(B, Q, state_str, prev_weather, prev_opp_action, depth=4, margin=5.0):
    """
    Hybrid policy for MAX:
      - Default: greedy Q-learning action
      - If triggers fire: consult minimax root values and override if clearly better

    Arguments:
      B: EnvBridge
      Q: learned Q-table mapping (state_key, action_str) -> float
      state_str: Prolog state string "state(...)"
      prev_weather: weather at START of previous lap, or None
      prev_opp_action: opponent action taken on previous lap, or None
      depth: minimax search depth
      margin: minimax must beat Q by at least this much to override

    Returns:
      action_str: chosen action ("stay" or "pit(x)")
      info: dict with debugging and stats fields
    """
    sk = parse_state_key(state_str)
    legal = B.legal_actions(state_str, "max")
    a_q, q_val = greedy_q_action(Q, sk, legal)

    fired, trig = triggers_fire(sk, prev_weather, prev_opp_action)

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