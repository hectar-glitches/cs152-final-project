from pathlib import Path
from pyswip import Prolog


class EnvBridge:
    """Bridge class for calling Prolog predicates from Python.

    This wrapper normalizes Python/Prolog conversions and exposes convenience
    methods for environment setup, transitions, rewards, terminal checks, and
    minimax helpers.
    """

    def __init__(self, prolog_dir: str | Path):
        """Initialize the bridge and consult required Prolog files.

        Args:
            prolog_dir: Directory containing the Prolog source files.

        Raises:
            FileNotFoundError: If any required Prolog file is missing.
        """
        self.prolog = Prolog()
        prolog_dir = Path(prolog_dir).resolve()

        self._consult(prolog_dir / "f1_drivers.pl")
        self._consult(prolog_dir / "f1_rules.pl")
        self._consult(prolog_dir / "f1_env.pl")
        self._consult(prolog_dir / "f1_minimax.pl")

        self._ensure_to_pl()

    def _consult(self, file_path: Path):
        """Consult a Prolog file into the current Prolog engine.

        Args:
            file_path: Absolute or relative path to a `.pl` file.

        Raises:
            FileNotFoundError: If `file_path` does not exist.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Missing Prolog file: {file_path}")
        self.prolog.consult(str(file_path))

    def _ensure_to_pl(self):
        """Ensure helper predicate `to_pl/2` exists in Prolog.

        If `to_pl/2` is missing, this defines it using SWI-Prolog's
        `term_string/2`.
        """
        if not list(self.prolog.query("current_predicate(to_pl/2).", maxresult=1)):
            self.prolog.assertz("to_pl(T,S) :- term_string(T,S).")

    @staticmethod
    def _as_str(x) -> str:
        """Convert PySWIP values into plain Python strings.

        Args:
            x: Value returned from PySWIP query bindings.

        Returns:
            A normalized string value. Returns an empty string for `None`.
        """
        if x is None:
            return ""
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="ignore")
        return str(x)

    @staticmethod
    def _escape_single_quotes(s: str) -> str:
        """Escape backslashes and single quotes for Prolog string literals.

        Args:
            s: Raw string to embed in a Prolog single-quoted string.

        Returns:
            Escaped string safe for `term_string(S,'...')` usage.
        """
        return s.replace("\\", "\\\\").replace("'", "\\'")

    def q1(self, query: str):
        """Run a Prolog query and return the first solution.

        Args:
            query: Prolog query string.

        Returns:
            The first solution dictionary, or `None` if no solution exists.
        """
        sols = list(self.prolog.query(query, maxresult=1))
        return sols[0] if sols else None

    def set_track(self, track: str) -> None:
        """Set the active track in the Prolog knowledge base.

        Args:
            track: Prolog atom/string representing the track.
        """
        self.q1(f"retractall(current_track(_)), assertz(current_track({track})).")

    def set_setup(self, fw: int, rw: int, rh: str) -> None:
        """Set current vehicle setup values in the knowledge base.

        Args:
            fw: Front wing value.
            rw: Rear wing value.
            rh: Ride height value represented as a Prolog term.
        """
        self.q1("retractall(setup(_,_,_)).")
        self.q1(f"assertz(setup({fw},{rw},{rh})).")

    def set_driver(self, driver: str) -> None:
        """Set the current driver in the knowledge base.

        Args:
            driver: Prolog atom/string identifying the driver.
        """
        self.q1("retractall(current_driver(_)).")
        self.q1(f"assertz(current_driver({driver})).")

    def init_state(self, laps: int, weather: str, my_tyre: str, opp_tyre: str) -> str:
        """Construct an initial game state via Prolog.

        Args:
            laps: Number of laps in the scenario.
            weather: Initial weather term.
            my_tyre: Current player's starting tyre term.
            opp_tyre: Opponent's starting tyre term.

        Returns:
            Serialized Prolog state string, or an empty string on failure.
        """
        sol = self.q1(f"init_state({laps},{weather},{my_tyre},{opp_tyre}, S), to_pl(S,SStr).")
        return self._as_str(sol["SStr"]) if sol else ""

    def legal_actions(self, state_str: str, player: str) -> list[str]:
        """Get legal actions for a player from a serialized state.

        Args:
            state_str: Serialized Prolog state term.
            player: Prolog player term.

        Returns:
            List of serialized action terms. Empty if query fails.
        """
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
        """Apply an action for a player and return the next state.

        Args:
            state_str: Serialized current state term.
            player: Prolog player term.
            action_str: Serialized action term.

        Returns:
            Serialized next state string, or `None` if the transition fails.
        """
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
        """Compute immediate reward for taking an action from a state.

        Args:
            state_str: Serialized current state term.
            player: Prolog player term.
            action_str: Serialized action term.

        Returns:
            Reward as a float. Returns `0.0` if query fails.
        """
        state_str = self._as_str(state_str)
        action_str = self._as_str(action_str)
        s_safe = self._escape_single_quotes(state_str)

        sol = self.q1(
            f"term_string(S,'{s_safe}'), "
            f"step_reward(S,{player},{action_str}, R)."
        )
        return float(sol["R"]) if sol else 0.0

    def terminal(self, state_str: str) -> tuple[bool, float | None]:
        """Check whether a state is terminal and get its value.

        Args:
            state_str: Serialized state term.

        Returns:
            A tuple `(is_terminal, value)`, where `value` is `None` when the
            state is non-terminal.
        """
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
        """Set weather in a serialized state and return updated state.

        Args:
            state_str: Serialized current state term.
            new_weather: Prolog weather term.

        Returns:
            Serialized updated state string. If query fails, returns input state.
        """
        state_str = self._as_str(state_str)
        s_safe = self._escape_single_quotes(state_str)

        sol = self.q1(
            f"term_string(S,'{s_safe}'), "
            f"set_weather(S,{new_weather}, S2), "
            f"to_pl(S2,SStr)."
        )
        return self._as_str(sol["SStr"]) if sol else state_str

    def minimax_best_player(self, state_str: str, depth: int, player: str) -> tuple[str, float]:
        """Get minimax best action and value for a player.

        Args:
            state_str: Serialized root state term.
            depth: Search depth.
            player: Prolog player term.

        Returns:
            Tuple `(best_action, value)`. Returns `("none", 0.0)` on failure.
        """
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
        """Get minimax value estimates for all root actions.

        Args:
            state_str: Serialized root state term.
            depth: Search depth.
            player: Prolog player term.

        Returns:
            List of `(action, value)` tuples.
        """
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

    def _parse_list_string(self, s: str) -> list[str]:
        """Parse a Prolog list string into top-level items.

        Args:
            s: String representation of a Prolog list.

        Returns:
            List of top-level item strings.
        """
        s = s.strip()
        if not (s.startswith("[") and s.endswith("]")):
            return []
        inner = s[1:-1].strip()
        if not inner:
            return []
        return self._split_top_level(inner)

    def _parse_action_value_pairs(self, s: str) -> list[tuple[str, float]]:
        """Parse `action_value(Action,Value)` list terms from string form.

        Args:
            s: String representation of a Prolog list.

        Returns:
            Parsed `(action, value)` pairs. Malformed items are skipped.
        """
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
        """Split a term string by commas at top level only.

        Parentheses and brackets are tracked so nested commas are ignored.

        Args:
            s: Input string containing comma-separated terms.

        Returns:
            List of top-level segments.
        """
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
    """Create an `EnvBridge` using the repository's default Prolog folder.

    Returns:
        Initialized `EnvBridge` pointing at `../prolog` relative to this file.
    """
    here = Path(__file__).resolve().parent
    prolog_dir = here.parent / "prolog"
    return EnvBridge(prolog_dir)