# python/q_learning.py
import random
from collections import defaultdict

from env_bridge import make_bridge


WEATHERS = ["dry", "drizzle", "wet"]
AGE_BUCKETS = ["fresh", "ok", "old"]
PLANK_BUCKETS = ["safe", "warn", "critical", "illegal"]


def parse_state_key(state_str: str):
    """
    Turn the Prolog state term string into a compact, hashable state key for Q-learning.

    Example state:
    state(5,drizzle,my(soft,0,[soft],0.0,0,0.0),opp(...))

    We extract:
      laps_left,
      weather,
      my_tyre,
      my_age_bucket,
      my_plank_bucket

    This is deliberately simple. You can add opponent tyre/age later.
    """
    # crude parsing via string splits (fast and good enough for this project)
    # state(L, W, my(Tyre, Age, Used, PW, Warm, Time), opp(...))

    # get laps_left and weather
    inside = state_str[len("state("):-1]  # remove "state(" and trailing ")"
    parts = split_top_level_commas(inside)
    laps_left = int(parts[0])
    weather = parts[1]

    # parse my(...)
    my_term = parts[2]  # "my(...)"
    my_inside = my_term[len("my("):-1]
    my_parts = split_top_level_commas(my_inside)

    my_tyre = my_parts[0]
    my_age = int(my_parts[1])
    my_pw = float(my_parts[3])

    my_age_bucket = age_bucket(my_age)
    my_plank_bucket = plank_bucket(my_pw)

    return (laps_left, weather, my_tyre, my_age_bucket, my_plank_bucket)


def split_top_level_commas(s: str):
    """Split by commas, but ignore commas inside (...) or [...]"""
    out = []
    depth_paren = 0
    depth_brack = 0
    buf = []
    for ch in s:
        if ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch == "[":
            depth_brack += 1
        elif ch == "]":
            depth_brack -= 1

        if ch == "," and depth_paren == 0 and depth_brack == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf).strip())
    return out


def age_bucket(age: int) -> str:
    if age == 0:
        return "fresh"
    if 1 <= age <= 8:
        return "ok"
    return "old"


def plank_bucket(pw: float) -> str:
    # keep consistent with your Prolog plank_status thresholds (approx)
    # plank_limit = 1.0
    if pw <= 0.6:
        return "safe"
    if pw <= 0.9:
        return "warn"
    if pw <= 1.0:
        return "critical"
    return "illegal"


def sample_weather_next(B, track: str, regime: str, w: str) -> str:
    q = f"findall(p(NW,P), transition_prob({track},{regime},{w},NW,P), L)."
    sol = B.q1(q)
    L = sol["L"]

    choices = []
    weights = []

    for term in L:
        t = str(term).strip()
        if t.startswith("p(") and t.endswith(")"):
            inside = t[2:-1]
            nw_str, p_str = inside.split(",", 1)
            choices.append(nw_str.strip())
            weights.append(float(p_str.strip()))
        else:
            raise ValueError(f"Unexpected transition term: {term}")

    return random.choices(choices, weights=weights, k=1)[0]


def epsilon_greedy_action(Q, state_key, actions, eps: float):
    if not actions:
        return "stay"
    if random.random() < eps:
        return random.choice(actions)
    # greedy
    best_a = actions[0]
    best_q = Q[(state_key, best_a)]
    for a in actions[1:]:
        qa = Q[(state_key, a)]
        if qa > best_q:
            best_q = qa
            best_a = a
    return best_a


def train_q_learning(
    episodes=500,
    alpha=0.2,
    gamma=0.95,
    epsilon=0.1,
    laps=10,
    start_weather="drizzle",
    my_start_tyre="soft",
    opp_start_tyre="soft",
    regime="unstable",
):
    B = make_bridge()

    # Configure once (you can vary these per scenario later)
    B.set_track("interlagos")
    B.set_setup(3, 3, "med")
    B.set_driver("max")

    Q = defaultdict(float)

    for ep in range(episodes):
        S = B.init_state(laps, start_weather, my_start_tyre, opp_start_tyre)

        done, term_val = B.terminal(S)
        step_count = 0

        while not done:
            sk = parse_state_key(S)
            actions = B.legal_actions(S, "max")
            a = epsilon_greedy_action(Q, sk, actions, epsilon)

            # reward for MAX move (utility delta)
            r = B.step_reward(S, "max", a)

            # step env with MAX action
            S2 = B.apply_action(S, "max", a)

            # stochastic weather update
            # extract current weather from S2 quickly
            w2 = parse_state_key(S2)[1]
            w3 = sample_weather_next(B, "interlagos", regime, w2)
            S2 = B.set_weather(S2, w3)

            # opponent move (baseline): stay
            opp_action = "stay"
            S3 = B.apply_action(S2, "min", opp_action)

            # weather again (optional; you can also do once per full lap instead)
            w4 = parse_state_key(S3)[1]
            w5 = sample_weather_next(B, "interlagos", regime, w4)
            S3 = B.set_weather(S3, w5)

            # next state + terminal check
            done, term_val = B.terminal(S3)
            sk2 = parse_state_key(S3)

            # standard Q-learning update
            if done:
                target = r + gamma * (term_val if term_val is not None else 0.0)
            else:
                next_actions = B.legal_actions(S3, "max")
                if next_actions:
                    max_next = max(Q[(sk2, a2)] for a2 in next_actions)
                else:
                    max_next = 0.0
                target = r + gamma * max_next

            Q[(sk, a)] = (1 - alpha) * Q[(sk, a)] + alpha * target

            S = S3
            step_count += 1
            if step_count > 500:
                break

        # optional: decay epsilon slowly
        # epsilon = max(0.01, epsilon * 0.999)

        if (ep + 1) % 50 == 0:
            print(f"Episode {ep+1}/{episodes} finished. terminal={term_val}")

    return Q


if __name__ == "__main__":
    Q = train_q_learning(
        episodes=300,
        alpha=0.2,
        gamma=0.95,
        epsilon=0.2,
        laps=10,
        start_weather="drizzle",
        my_start_tyre="soft",
        opp_start_tyre="soft",
        regime="unstable",
    )

    print("Learned Q entries:", len(Q))