# python/env_bridge.py
from pathlib import Path
from pyswip import Prolog


class EnvBridge:
    """
    Minimal Prolog to Python bridge.
    Keeps the State as a Prolog term string (e.g., "state(5,drizzle,my(...),opp(...))")
    and just passes it back into Prolog unchanged.
    """

    def __init__(self, project_root: str | Path):
        self.root = Path(project_root).resolve()
        self.prolog = Prolog()
        self._consult()

    def _consult(self) -> None:
        prolog_dir = self.root / "prolog"

        # Consult in a simple, explicit order
        for fname in ["f1_drivers.pl", "f1_rules.pl", "f1_env.pl", "f1_minimax.pl"]:
            fpath = prolog_dir / fname
            if not fpath.exists():
                raise FileNotFoundError(f"Missing Prolog file: {fpath}")
            self.prolog.consult(str(fpath))

    def q1(self, query: str):
        sols = list(self.prolog.query(query, maxresult=1))
        if not sols:
            return None
        sol = sols[0]
        # normalize any bytes values to str
        for k, v in list(sol.items()):
            if isinstance(v, (bytes, bytearray)):
                sol[k] = v.decode("utf-8")
        return sol

    # config
    def set_track(self, track: str) -> None:
        self.q1("retractall(current_track(_)).")
        self.q1(f"assertz(current_track({track})).")

    def set_setup(self, fw: int, rw: int, rh: str) -> None:
        self.q1("retractall(setup(_,_,_)).")
        self.q1(f"assertz(setup({fw},{rw},{rh})).")

    def set_driver(self, driver: str) -> None:
        self.q1("retractall(current_driver(_)).")
        self.q1(f"assertz(current_driver({driver})).")

    # state
    def init_state(self, laps, weather, my_tyre, opp_tyre) -> str:
        sol = self.q1(f"init_state({laps},{weather},{my_tyre},{opp_tyre}, S), to_pl(S, SStr).")
        return sol["SStr"]

    # env API
    def legal_actions(self, state: str, player: str) -> list[str]:
        sol = self.q1(f"legal_actions({state},{player}, Actions).")
        if not sol:
            return []
        return [str(a) for a in sol["Actions"]]

    def apply_action(self, state, player, action) -> str:
        sol = self.q1(f"apply_action({state},{player},{action}, S2), to_pl(S2, SStr).")
        return sol["SStr"]

    def step_reward(self, state: str, player: str, action: str) -> float:
        sol = self.q1(f"step_reward({state},{player},{action}, R).")
        if not sol:
            raise RuntimeError(f"step_reward/4 failed for action={action}")
        return float(sol["R"])

    def terminal(self, state: str) -> tuple[bool, float | None]:
        sol = self.q1(f"terminal({state}, V).")
        if not sol:
            return (False, None)
        return (True, float(sol["V"]))

    def evaluate(self, state: str) -> float:
        sol = self.q1(f"evaluate({state}, V).")
        if not sol:
            raise RuntimeError("evaluate/2 failed")
        return float(sol["V"])

    def set_weather(self, state, new_weather) -> str:
        sol = self.q1(f"set_weather({state},{new_weather}, S2), to_pl(S2, SStr).")
        return sol["SStr"]

    # minimax
    def minimax_best(self, state: str, depth: int) -> tuple[str, float]:
        sol = self.q1(f"minimax_best({state},{depth}, A, V).")
        if not sol:
            return ("none", 0.0)
        return (str(sol["A"]), float(sol["V"]))
    
    def root_values(self, state: str, depth: int, player: str):
        """
        Returns list of (action_str, value_float) from Prolog root_values/4.
        Expects Prolog predicate: root_values(State, Depth, Player, Pairs).
        Pairs look like: [action_value(stay, -1.7), action_value(pit(inter), -19.6), ...]
        """
        sol = self.q1(f"root_values({state},{depth},{player}, Pairs).")
        if not sol:
            return []
        pairs = sol["Pairs"]
        out = []
        for item in pairs:
            s = str(item).strip()
            # expected "action_value(stay,-1.7)" or "action_value(pit(inter),-19.6)"
            inside = s[len("action_value("):-1]
            a_str, v_str = inside.rsplit(",", 1)
            out.append((a_str.strip(), float(v_str.strip())))
        return out


def make_bridge() -> EnvBridge:
    """
    Assumes file is python/env_bridge.py and project layout is:
      project_root/
        prolog/
        python/
    """
    root = Path(__file__).resolve().parents[1]
    return EnvBridge(root)