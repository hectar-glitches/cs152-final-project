# python/q_learning.py
import random
import pickle
from collections import defaultdict

from env_bridge import make_bridge


def split_top_level_commas(s: str):
    """Split by commas, ignoring commas inside (...) or [...]"""
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
    if pw <= 0.6:
        return "safe"
    if pw <= 0.9:
        return "warn"
    if pw <= 1.0:
        return "critical"
    return "illegal"


def parse_state_key(state_str: str):
    """
    Produce a compact, hashable Q-learning state key from the Prolog state string.

    Arguments:
      state_str: Prolog term as a string:
        "state(L,Weather,my(...),opp(...))"

    Returns:
      tuple:
        (laps_left, weather,
         my_tyre, my_age_bucket, my_plank_bucket,
         opp_tyre, opp_age_bucket)
    """
    inside = state_str[len("state("):-1]
    parts = split_top_level_commas(inside)

    laps_left = int(parts[0])
    weather = parts[1]

    my_term = parts[2]
    my_inside = my_term[len("my("):-1]
    my_parts = split_top_level_commas(my_inside)
    my_tyre = my_parts[0]
    my_age = int(my_parts[1])
    my_pw = float(my_parts[3])

    opp_term = parts[3]
    opp_inside = opp_term[len("opp("):-1]
    opp_parts = split_top_level_commas(opp_inside)
    opp_tyre = opp_parts[0]
    opp_age = int(opp_parts[1])

    return (
        laps_left,
        weather,
        my_tyre,
        age_bucket(my_age),
        plank_bucket(my_pw),
        opp_tyre,
        age_bucket(opp_age),
    )


def sample_weather_next(B, track: str, regime: str, w: str) -> str:
    """
    Sample next weather state from Prolog transition_prob/5.
    """
    q = f"findall(p(NW,P), transition_prob({track},{regime},{w},NW,P), L)."
    sol = B.q1(q)
    L = sol["L"]

    choices = []
    weights = []
    for term in L:
        t = str(term).strip()
        inside = t[2:-1]  # "NW,P"
        nw_str, p_str = inside.split(",", 1)
        choices.append(nw_str.strip())
        weights.append(float(p_str.strip()))

    return random.choices(choices, weights=weights, k=1)[0]


def epsilon_greedy_action(Q, state_key, actions, eps: float):
    if not actions:
        return "stay"
    if random.random() < eps:
        return random.choice(actions)
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
    epsilon=0.2,
    laps=30,
    start_weather="drizzle",
    my_start_tyre="soft",
    opp_start_tyre="soft",
    regime="unstable",
    track="interlagos",
    setup=(3, 3, "med"),
    driver="max",
):
    """
    Vanilla Q-learning for MAX with a fixed opponent (stationary) and Markov weather.

    Timing convention (matches run_race):
      - MAX acts
      - MIN acts (default = stay)
      - weather transitions ONCE per full lap

    Returns:
      Q: defaultdict(float) mapping (state_key, action_str) -> q_value
    """
    B = make_bridge()
    B.set_track(track)
    B.set_setup(*setup)
    B.set_driver(driver)

    Q = defaultdict(float)

    for ep in range(episodes):
        S = B.init_state(laps, start_weather, my_start_tyre, opp_start_tyre)

        step_count = 0
        while True:
            done, term_val = B.terminal(S)
            if done:
                break

            sk = parse_state_key(S)
            actions = B.legal_actions(S, "max")
            a = epsilon_greedy_action(Q, sk, actions, epsilon)

            r = B.step_reward(S, "max", a)
            S1 = B.apply_action(S, "max", a)

            # fixed opponent during training
            opp_action = "stay"
            S2 = B.apply_action(S1, "min", opp_action)

            # weather transition once per lap
            w_now = parse_state_key(S2)[1]
            w_next = sample_weather_next(B, track, regime, w_now)
            S3 = B.set_weather(S2, w_next)

            done2, term_val2 = B.terminal(S3)
            sk2 = parse_state_key(S3)

            if done2:
                target = r + gamma * (term_val2 if term_val2 is not None else 0.0)
            else:
                next_actions = B.legal_actions(S3, "max")
                max_next = max((Q[(sk2, a2)] for a2 in next_actions), default=0.0)
                target = r + gamma * max_next

            Q[(sk, a)] = (1 - alpha) * Q[(sk, a)] + alpha * target

            S = S3
            step_count += 1
            if step_count > 1000:
                break

        if (ep + 1) % 50 == 0:
            print(f"Episode {ep+1}/{episodes} finished. terminal={term_val}")

    return Q


if __name__ == "__main__":
    Q = train_q_learning(
        episodes=300,
        alpha=0.2,
        gamma=0.95,
        epsilon=0.2,
        laps=30,
        start_weather="drizzle",
        my_start_tyre="soft",
        opp_start_tyre="soft",
        regime="unstable",
        track="interlagos",
        setup=(3, 3, "med"),
        driver="max",
    )

    with open("python/q_table.pkl", "wb") as f:
        pickle.dump(Q, f)
    print("Saved Q to python/q_table.pkl")
    print("Learned Q entries:", len(Q))