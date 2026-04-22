# python/run_race.py
import pickle
import random

from env_bridge import make_bridge
from q_learning import parse_state_key, sample_weather_next
from hybrid_policy import choose_action_hybrid


def run_one_race_hybrid(
    Q,
    driver="max",
    laps=30,
    start_weather="drizzle",
    regime="unstable",
    depth=4,
    setup=(3, 3, "med"),
    track="interlagos",
    seed=42,
    verbose=True,
):
    random.seed(seed)

    B = make_bridge()
    B.set_track(track)
    B.set_setup(*setup)
    B.set_driver(driver)

    S = B.init_state(laps, start_weather, "soft", "soft")

    prev_weather = None
    step = 0

    # stats counters
    pits_max = 0
    pits_min = 0
    mm_used = 0
    overrides = 0
    trig_counts = {"pit_window": 0, "weather_transition": 0, "dsq_risk": 0}

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
                "mm_used": mm_used,
                "overrides": overrides,
                "trigger_counts": trig_counts,
                "steps": step,
            }

        # MAX (hybrid)
        action, info = choose_action_hybrid(B, Q, S, prev_weather, depth=depth, margin=5.0)

        # stats: triggers + minimax usage
        for k, fired in info["trigger"].items():
            if fired:
                trig_counts[k] += 1
        if info["used"] == "minimax":
            mm_used += 1
        if info.get("override", False):
            overrides += 1
        if action.startswith("pit("):
            pits_max += 1

        if verbose:
            print(f"[{step}] MAX action={action} used={info['used']} trigger={info['trigger']}")

        S = B.apply_action(S, "max", action)

        # MIN (minimax opponent)
        opp_action, opp_val = B.minimax_best_player(S, depth, "min")
        if opp_action == "none":
            opp_action = "stay"
        if opp_action.startswith("pit("):
            pits_min += 1

        if verbose:
            print(f"[{step}] MIN action={opp_action}")

        S = B.apply_action(S, "min", opp_action)

        # weather update again
        w_now = parse_state_key(S)[1]
        w_next = sample_weather_next(B, track, regime, w_now)
        S = B.set_weather(S, w_next)
        if verbose:
            print(f"    Weather: {w_next}")

        step += 1

        prev_weather = w_next


if __name__ == "__main__":
    # load Q
    with open("python/q_table.pkl", "rb") as f:
        Q = pickle.load(f)

    run_one_race_hybrid(Q)