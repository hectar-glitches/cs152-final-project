% test_minimax.pl: test cases for minimax implementation

:- use_module(library(lists)).
:- ['f1_env.pl'].

other_player(max, min).
other_player(min, max).

% Public entry point
minimax_best(State, Depth, BestAction, BestValue) :-
    minimax(State, Depth, max, BestAction, BestValue).

% Terminal
minimax(State, _Depth, _Player, none, Value) :-
    terminal(State, Value),
    !.

% Depth limit
minimax(State, 0, _Player, none, Value) :-
    evaluate(State, Value),
    !.

% Main recursive step
minimax(State, Depth, Player, BestAction, BestValue) :-
    Depth > 0,
    legal_actions(State, Player, Actions),
    NextDepth is Depth - 1,

    % Build action-value pairs, but SKIP actions that fail
    findall(action_value(A, V),
        (
            member(A, Actions),
            safe_action_value(State, Player, A, NextDepth, V)
        ),
        Pairs),

    % If everything failed, fall back to heuristic instead of failing
    ( Pairs = [] ->
        BestAction = none,
        evaluate(State, BestValue)
    ; choose_best(Player, Pairs, action_value(BestAction, BestValue))
    ),
    !.

% Compute value for ONE action safely (fails if action cannot be applied)
safe_action_value(State, Player, Action, NextDepth, Value) :-
    apply_action(State, Player, Action, NextState),
    step_reward(State, Player, Action, R),
    other_player(Player, NextPlayer),
    minimax(NextState, NextDepth, NextPlayer, _Ignored, V2),
    Value is R + V2.

% Choose best depending on player
choose_best(max, [H|T], Best) :-
    foldl(max_pair, T, H, Best).
choose_best(min, [H|T], Best) :-
    foldl(min_pair, T, H, Best).

max_pair(action_value(A1,V1), action_value(_A2,V2), action_value(A1,V1)) :-
    V1 >= V2, !.
max_pair(_X, Y, Y).

min_pair(action_value(A1,V1), action_value(_A2,V2), action_value(A1,V1)) :-
    V1 =< V2, !.
min_pair(_X, Y, Y).

run :-
    writeln('Starting test...'),
    retractall(current_track(_)), assertz(current_track(interlagos)),
    retractall(setup(_,_,_)), assertz(setup(3,3,med)),
    retractall(current_driver(_)), assertz(current_driver(max)),
    init_state(5, drizzle, soft, soft, S),
    writeln(state=S),
    minimax_best(S, 4, A, V),
    writeln(best_action=A),
    writeln(value=V),
    halt.