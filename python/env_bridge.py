# python/env_bridge.py
from pathlib import Path
from pyswip import Prolog


class EnvBridge:
    """
    Thin wrapper around Prolog predicates.

    Important:
    - We always pass states/actions as *plain Python str* containing a Prolog term.
    - PySWIP sometimes returns Prolog strings as bytes. We normalize those to str.
    """

    def __init__(self, prolog_dir: str | Path):
        self.prolog = Prolog()
        prolog_dir = Path(prolog_dir).resolve()

        self._consult(prolog_dir / "f1_drivers.pl")
        self._consult(prolog_dir / "f1_rules.pl")
        self._consult(prolog_dir / "f1_env.pl")
        self._consult(prolog_dir / "f1_minimax.pl")

        self._ensure_to_pl()

    # internal helpers
    def _consult(self, file_path: Path):
        if not file_path.exists():
            raise FileNotFoundError(f"Missing Prolog file: {file_path}")
        self.prolog.consult(str(file_path))

    def _ensure_to_pl(self):
        # term_string/2 exists in SWI, but we define to_pl/2 if missing
        if not list(self.prolog.query("current_predicate(to_pl/2).", maxresult=1)):
            self.prolog.assertz("to_pl(T,S) :- term_string(T,S).")

    @staticmethod
    def _as_str(x) -> str:
        """Convert PySWIP return types into plain Python str."""
        if x is None:
            return ""
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="ignore")
        return str(x)

    @staticmethod
    def _escape_single_quotes(s: str) -> str:
        """Make a string safe inside term_string(S,'...')."""
        return s.replace("\\", "\\\\").replace("'", "\\'")

    def q1(self, query: str):
        sols = list(self.prolog.query(query, maxresult=1))
        return sols[0] if sols else None

    # KB configuration
    def set_track(self, track: str) -> None:
        self.q1(f"retractall(current_track(_)), assertz(current_track({track})).")

    def set_setup(self, fw: int, rw: int, rh: str) -> None:
        self.q1("retractall(setup(_,_,_)).")
        self.q1(f"assertz(setup({fw},{rw},{rh})).")

    def set_driver(self, driver: str) -> None:
        self.q1("retractall(current_driver(_)).")
        self.q1(f"assertz(current_driver({driver})).")

    # Environment predicates
    def init_state(self, laps: int, weather: str, my_tyre: str, opp_tyre: str) -> str:
        sol = self.q1(f"init_state({laps},{weather},{my_tyre},{opp_tyre}, S), to_pl(S,SStr).")
        return self._as_str(sol["SStr"]) if sol else ""

    def legal_actions(self, state_str: str, player: str) -> list[str]:
        state_str = self._as_str(state_str)
        s_safe = self._escape_single_quotes(state_str)

        sol = self.q1(
            f"term_string(S,'{s_safe}'), "
            f"legal_actions(S,{player},Acts), "
            f"findall(A, member(A,Acts), L), "
            f"to_pl(L,LStr)."
        )
        if not sol:
            return []
        return self._parse_list_string(self._as_str(sol["LStr"]))

    def apply_action(self, state_str: str, player: str, action_str: str) -> str | None:
        state_str = self._as_str(state_str)
        action_str = self._as_str(action_str)
        s_safe = self._escape_single_quotes(state_str)

        sol = self.q1(
            f"term_string(S,'{s_safe}'), "
            f"apply_action(S,{player},{action_str}, S2), "
            f"to_pl(S2,SStr)."
        )
        return self._as_str(sol["SStr"]) if sol else None

    def step_reward(self, state_str: str, player: str, action_str: str) -> float:
        state_str = self._as_str(state_str)
        action_str = self._as_str(action_str)
        s_safe = self._escape_single_quotes(state_str)

        sol = self.q1(
            f"term_string(S,'{s_safe}'), "
            f"step_reward(S,{player},{action_str}, R)."
        )
        return float(sol["R"]) if sol else 0.0

    def terminal(self, state_str: str) -> tuple[bool, float | None]:
        state_str = self._as_str(state_str)
        s_safe = self._escape_single_quotes(state_str)

        sol = self.q1(
            f"term_string(S,'{s_safe}'), "
            f"terminal(S,V)."
        )
        if not sol:
            return False, None
        return True, float(sol["V"])

    def set_weather(self, state_str: str, new_weather: str) -> str:
        state_str = self._as_str(state_str)
        s_safe = self._escape_single_quotes(state_str)

        sol = self.q1(
            f"term_string(S,'{s_safe}'), "
            f"set_weather(S,{new_weather}, S2), "
            f"to_pl(S2,SStr)."
        )
        return self._as_str(sol["SStr"]) if sol else state_str

    # Minimax helpers
    def minimax_best_player(self, state_str: str, depth: int, player: str) -> tuple[str, float]:
        state_str = self._as_str(state_str)
        s_safe = self._escape_single_quotes(state_str)

        sol = self.q1(
            f"term_string(S,'{s_safe}'), "
            f"minimax_best_player(S,{depth},{player},A,V)."
        )
        if not sol:
            return "none", 0.0
        return self._as_str(sol["A"]), float(sol["V"])

    def root_values(self, state_str: str, depth: int, player: str) -> list[tuple[str, float]]:
        state_str = self._as_str(state_str)
        s_safe = self._escape_single_quotes(state_str)

        sol = self.q1(
            f"term_string(S,'{s_safe}'), "
            f"root_values(S,{depth},{player},Pairs), "
            f"to_pl(Pairs,PStr)."
        )
        if not sol:
            return []
        return self._parse_action_value_pairs(self._as_str(sol["PStr"]))

    # parsing helpers
    def _parse_list_string(self, s: str) -> list[str]:
        s = s.strip()
        if not (s.startswith("[") and s.endswith("]")):
            return []
        inner = s[1:-1].strip()
        if not inner:
            return []
        return self._split_top_level(inner)

    def _parse_action_value_pairs(self, s: str) -> list[tuple[str, float]]:
        s = s.strip()
        if not (s.startswith("[") and s.endswith("]")):
            return []
        inner = s[1:-1].strip()
        if not inner:
            return []
        items = self._split_top_level(inner)
        out = []
        for it in items:
            it = it.strip()
            if not it.startswith("action_value(") or not it.endswith(")"):
                continue
            inside = it[len("action_value("):-1]
            parts = self._split_top_level(inside)
            if len(parts) != 2:
                continue
            a_str = parts[0].strip()
            v_str = parts[1].strip()
            out.append((a_str, float(v_str)))
        return out

    def _split_top_level(self, s: str) -> list[str]:
        out = []
        buf = []
        depth_paren = 0
        depth_brack = 0
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
                out.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        out.append("".join(buf))
        return out


def make_bridge() -> EnvBridge:
    here = Path(__file__).resolve().parent
    prolog_dir = here.parent / "prolog"
    return EnvBridge(prolog_dir)