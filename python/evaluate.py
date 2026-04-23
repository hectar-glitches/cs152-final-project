# python/evaluate.py
"""Evaluate hybrid race policy performance across drivers and seeds."""

import pickle
import statistics as stats

from run_race import run_one_race_hybrid


def summarize(values):
    """Compute basic summary statistics for numeric values.

    Args:
        values: Iterable of numeric values.

    Returns:
        A dictionary containing:
            - mean: Arithmetic mean.
            - stdev: Population standard deviation.
            - min: Minimum value.
            - max: Maximum value.
    """
    return {
        "mean": stats.mean(values),
        "stdev": stats.pstdev(values),
        "min": min(values),
        "max": max(values),
    }


def main():
    """Run repeated race evaluations and print per-driver aggregate metrics.

    This function loads a Q-table from disk, defines a fixed scenario, runs
    multiple seeded simulations for each driver, and prints utility, DSQ rate,
    pit-stop averages, and minimax consultation/override averages.
    """
    with open("python/q_table.pkl", "rb") as f:
        Q = pickle.load(f)

    drivers = ["max", "lewis", "lando", "charles", "george"]

    scenario = dict(
        laps=55,
        start_weather="drizzle",
        regime="unstable",
        depth=4,
        setup=(3, 3, "high"),
        track="interlagos",
    )

    runs_per_driver = 30
    print("Scenario:", scenario)
    print("Runs per driver:", runs_per_driver)
    print("")

    for d in drivers:
        utilities = []
        dsq = 0
        pits_max = []
        pits_min = []
        mm_consults = []
        mm_overrides = []

        for i in range(runs_per_driver):
            seed = 1000 + i
            result = run_one_race_hybrid(
                Q=Q,
                driver=d,
                seed=seed,
                verbose=False,
                **scenario,
            )

            u = result["terminal_value"]
            utilities.append(u)

            if u is not None and abs(u) >= 900:
                dsq += 1

            pits_max.append(result.get("pits_max", 0))
            pits_min.append(result.get("pits_min", 0))
            mm_consults.append(result.get("mm_consults", 0))
            mm_overrides.append(result.get("mm_overrides", 0))

        s = summarize(utilities)
        print(f"Driver: {d}")
        print(f"Utility: mean={s['mean']:.2f} stdev={s['stdev']:.2f} min={s['min']:.2f} max={s['max']:.2f}")
        print(f"DSQ rate: {dsq}/{runs_per_driver} = {100.0*dsq/runs_per_driver:.1f}%")
        print(f"Avg pits (MAX): {stats.mean(pits_max):.2f}")
        print(f"Avg pits (MIN): {stats.mean(pits_min):.2f}")
        print(f"Avg minimax-consults per race: {stats.mean(mm_consults):.2f}")
        print(f"Avg minimax-overrides per race: {stats.mean(mm_overrides):.2f}")
        print("")


if __name__ == "__main__":
    main()