import pickle
import random

from env_bridge import make_bridge
from q_learning import parse_state_key, sample_weather_next
from hybrid_policy import choose_action_hybrid


def sanitize_action(action, legal_actions):
    """Sanitize an action so it is always safe to pass into Prolog apply_action/4.

    Prolog can fail (and PySWIP returns None) if you call apply_action with an
    illegal action. Minimax can also return "none" when it fails to find a move.

    Args:
        action: Proposed action string, e.g. "stay", "pit(medium)", "none", or None.
        legal_actions: List of legal action strings for the current player/state.

    Returns:
        A legal action string. If the proposal is invalid, returns "stay".
    """
    if action is None:
        return "stay"
    if isinstance(action, str) and action.strip() == "none":
        return "stay"
    if action not in legal_actions:
        return "stay"
    return action


def run_one_race_hybrid(
    Q,
    driver="max",
    laps=55,
    start_weather="drizzle",
    regime="unstable",
    depth=4,
    setup=(3, 3, "high"),
    track="interlagos",
    seed=42,
    verbose=True,
):
    """Run one simulated race (lap-based) with a hybrid MAX policy.

    Behavior:
        - MAX uses Q-learning by default.
        - MAX consults minimax only when triggers fire (implemented in hybrid_policy.py).
        - MIN responds using minimax as an adversary.
        - Weather transitions ONCE per full lap (after MAX + MIN moves).

    Args:
        Q: Q-table mapping (state_key, action_str) -> float.
        driver: Driver id used by Prolog (e.g. "max", "lewis", "lando").
        laps: Number of laps to simulate.
        start_weather: Starting weather ("dry", "drizzle", "wet").
        regime: Forecast regime for Markov transitions ("stable" or "unstable").
        depth: Minimax depth (plies).
        setup: Tuple (front_wing, rear_wing, ride_height_tier).
        track: Track atom used in Prolog, e.g. "interlagos".
        seed: RNG seed for reproducible weather sampling.
        verbose: If True, print a trace.

    Returns:
        Dict with:
            terminal_value: float utility (MAX perspective).
            final_state: final Prolog state string.
            pits_max/pits_min: pit counts actually executed.
            mm_consults/mm_overrides: how often MAX consulted/overrode using minimax.
            trigger_counts: counts of triggers that fired.
            steps: number of completed laps.
    """
    random.seed(seed)

    B = make_bridge()
    B.set_track(track)
    B.set_setup(*setup)
    B.set_driver(driver)

    S = B.init_state(laps, start_weather, "soft", "soft")

    prev_weather = None
    prev_opp_action = None
    step = 0

    pits_max = 0
    pits_min = 0
    mm_consults = 0
    mm_overrides = 0
    trig_counts = {
        "pit_window": 0,
        "weather_transition": 0,
        "dsq_risk": 0,
        "opp_pitted": 0,
        "mismatch": 0,
    }

    while True:
        done, term_val = B.terminal(S)
        if done:
            if verbose:
                print("TERMINAL:", term_val)
                print("FINAL STATE:", S)
            return {
                "terminal_value": term_val,
                "final_state": S,
                "pits_max": pits_max,
                "pits_min": pits_min,
                "mm_consults": mm_consults,
                "mm_overrides": mm_overrides,
                "trigger_counts": trig_counts,
                "steps": step,
            }

        # Weather at START of lap (used for transition trigger)
        curr_weather = parse_state_key(S)[1]

        # ----------------
        # MAX (hybrid)
        # ----------------
        action_raw, info = choose_action_hybrid(
            B=B,
            Q=Q,
            state_str=S,
            prev_weather=prev_weather,
            prev_opp_action=prev_opp_action,
            depth=depth,
            margin=5.0,
        )

        # trigger stats
        for k, fired in info.get("trigger", {}).items():
            if fired and k in trig_counts:
                trig_counts[k] += 1
        if info.get("consulted_minimax", False):
            mm_consults += 1
        if info.get("override", False):
            mm_overrides += 1

        legal_max = B.legal_actions(S, "max")
        action = sanitize_action(action_raw, legal_max)

        if action.startswith("pit("):
            pits_max += 1

        if verbose:
            print("STATE (start lap):", S)
            print(f"[{step}] MAX action={action} used={info.get('used')} trigger={info.get('trigger')}")
            # uncomment if you want noisy debugging:
            # print("LEGAL MAX:", legal_max)

        S1 = B.apply_action(S, "max", action)
        if S1 is None:
            # last-resort fallback
            S1 = B.apply_action(S, "max", "stay")

        done, term_val = B.terminal(S1)
        if done:
            if verbose:
                print("TERMINAL:", term_val)
                print("FINAL STATE:", S1)
            return {
                "terminal_value": term_val,
                "final_state": S1,
                "pits_max": pits_max,
                "pits_min": pits_min,
                "mm_consults": mm_consults,
                "mm_overrides": mm_overrides,
                "trigger_counts": trig_counts,
                "steps": step,
            }

        # ----------------
        # MIN (minimax)
        # ----------------
        opp_action_raw, _ = B.minimax_best_player(S1, depth, "min")
        legal_min = B.legal_actions(S1, "min")
        opp_action = sanitize_action(opp_action_raw, legal_min)

        if opp_action.startswith("pit("):
            pits_min += 1

        if verbose:
            print(f"[{step}] MIN action={opp_action}")
            # uncomment if you want noisy debugging:
            # print("LEGAL MIN:", legal_min)

        S2 = B.apply_action(S1, "min", opp_action)
        if S2 is None:
            S2 = B.apply_action(S1, "min", "stay")

        # -----------------------------------
        # Weather transition ONCE per full lap
        # -----------------------------------
        w_now = parse_state_key(S2)[1]
        w_next = sample_weather_next(B, track, regime, w_now)
        S3 = B.set_weather(S2, w_next)

        if verbose:
            print(f"    Weather: {w_next}")

        # prep next lap
        prev_weather = curr_weather
        prev_opp_action = opp_action
        S = S3
        step += 1


if __name__ == "__main__":
    with open("python/q_table.pkl", "rb") as f:
        Q = pickle.load(f)
    run_one_race_hybrid(Q)