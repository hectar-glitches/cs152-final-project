# python/evaluate_drivers.py
import pickle
import statistics as stats

from run_race import run_one_race_hybrid


def summarize(values):
    return {
        "n": len(values),
        "mean": stats.mean(values),
        "stdev": stats.pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def main():
    # Load Q once
    with open("python/q_table.pkl", "rb") as f:
        Q = pickle.load(f)

    drivers = ["max", "lewis", "lando"]

    # Fixed scenario
    scenario = dict(
        laps=30,
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
        mm_used = []
        overrides = []

        for i in range(runs_per_driver):
            # seed changes each run so weather differs, but reproducible
            seed = 1000 + i

            result = run_one_race_hybrid(
                Q=Q,
                driver=d,
                seed=seed,
                verbose=False,
                **scenario
            )

            utilities.append(result["terminal_value"])

            # DSQ detection (your terminal assigns around +/-1000)
            if result["terminal_value"] is not None and abs(result["terminal_value"]) >= 900:
                dsq += 1

            pits_max.append(result.get("pits_max", 0))
            pits_min.append(result.get("pits_min", 0))
            mm_used.append(result.get("mm_used", 0))
            overrides.append(result.get("overrides", 0))

        u = summarize(utilities)

        print("Driver:", d)
        print("Utility: mean={:.2f} stdev={:.2f} min={:.2f} max={:.2f}".format(u["mean"], u["stdev"], u["min"], u["max"]))
        print("DSQ rate: {}/{} = {:.1f}%".format(dsq, runs_per_driver, 100.0 * dsq / runs_per_driver))
        print("Avg pits (MAX): {:.2f}".format(stats.mean(pits_max)))
        print("Avg pits (MIN): {:.2f}".format(stats.mean(pits_min)))
        print("Avg minimax-used per race: {:.2f}".format(stats.mean(mm_used)))
        print("Avg minimax-overrides per race: {:.2f}".format(stats.mean(overrides)))
        print("")


if __name__ == "__main__":
    main()