import random
from env_bridge import make_bridge


def sample_weather_next(B, track: str, regime: str, w: str) -> str:
    """
    Sample next weather using Prolog transition_prob/5.
    We parse results as strings like "p(dry,0.85)".
    """
    sol = B.q1(f"findall(p(NW,P), transition_prob({track},{regime},{w},NW,P), L).")
    L = sol["L"]

    choices, weights = [], []
    for term in L:
        t = str(term).strip()
        # expected: p(dry,0.85)
        inside = t[2:-1]  # drop "p(" and ")"
        nw_str, p_str = inside.split(",", 1)
        choices.append(nw_str.strip())
        weights.append(float(p_str.strip()))

    return random.choices(choices, weights=weights, k=1)[0]


def run_one_race(
    laps: int = 10,
    start_weather: str = "drizzle",
    regime: str = "unstable",
    depth: int = 4,
    my_start_tyre: str = "soft",
    opp_start_tyre: str = "soft",
    setup=(3, 3, "med"),
    driver: str = "max",
    track: str = "interlagos",
    sample_weather_each_ply: bool = True,
    seed: int | None = None,
    verbose: bool = True,
):
    """
    Both players use minimax at depth=4.
    Weather is sampled in Python between moves (chance handled by simulator, not minimax).
    """
    if seed is not None:
        random.seed(seed)

    B = make_bridge()

    # Configure Prolog run
    B.set_track(track)
    fw, rw, rh = setup
    B.set_setup(fw, rw, rh)
    B.set_driver(driver)

    # Initial state
    S = B.init_state(laps, start_weather, my_start_tyre, opp_start_tyre)

    pit_count_max = 0
    pit_count_min = 0
    step_idx = 0

    while True:
        done, Vt = B.terminal(S)
        if done:
            if verbose:
                print("TERMINAL value:", Vt)
            return {
                "terminal_value": Vt,
                "final_state": S,
                "pits_max": pit_count_max,
                "pits_min": pit_count_min,
                "steps": step_idx,
            }

        # MAX move
        Amax, Vmax = B.minimax_best(S, depth)
        if Amax == "none":
            Amax = "stay"

        if verbose:
            print(f"[{step_idx}] MAX chooses {Amax} (est={Vmax:.3f})")

        if Amax.startswith("pit("):
            pit_count_max += 1

        S = B.apply_action(S, "max", Amax)

        if sample_weather_each_ply:
            # sample weather after MAX move
            # easiest: parse weather from state string
            weather_now = str(S).split(",")[1].strip()  # state(L,Weather,...)
            w_next = sample_weather_next(B, track, regime, weather_now)
            S = B.set_weather(S, w_next)
            if verbose:
                print(f"    Weather -> {w_next}")

        # Check terminal after MAX move
        done, Vt = B.terminal(S)
        if done:
            if verbose:
                print("TERMINAL value:", Vt)
            return {
                "terminal_value": Vt,
                "final_state": S,
                "pits_max": pit_count_max,
                "pits_min": pit_count_min,
                "steps": step_idx + 1,
            }

        # MIN move
        Amin, Vmin = B.minimax_best(S, depth)
        if Amin == "none":
            Amin = "stay"

        if verbose:
            print(f"[{step_idx}] MIN chooses {Amin} (est={Vmin:.3f})")

        if Amin.startswith("pit("):
            pit_count_min += 1

        S = B.apply_action(S, "min", Amin)

        if sample_weather_each_ply:
            # sample weather after MIN move
            weather_now = str(S).split(",")[1].strip()
            w_next = sample_weather_next(B, track, regime, weather_now)
            S = B.set_weather(S, w_next)
            if verbose:
                print(f"    Weather -> {w_next}")

        step_idx += 1
        if step_idx > 500:
            # safety break
            if verbose:
                print("Safety break")
            return {
                "terminal_value": None,
                "final_state": S,
                "pits_max": pit_count_max,
                "pits_min": pit_count_min,
                "steps": step_idx,
            }


if __name__ == "__main__":
    result = run_one_race(
        laps=10,
        start_weather="drizzle",
        regime="unstable",
        depth=4,
        my_start_tyre="soft",
        opp_start_tyre="soft",
        setup=(3, 3, "med"),
        driver="max",
        track="interlagos",
        sample_weather_each_ply=True,
        seed=42,
        verbose=True,
    )
    print("\nSUMMARY:", result)