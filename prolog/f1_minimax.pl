% prolog/f1_minimax.pl
% Minimax search for F1 strategy:
%   MAX = you
%   MIN = opponent
%
% Uses environment predicates from f1_env.pl:
%   legal_actions(State, Player, Actions)
%   apply_action(State, Player, Action, NextState)
%   step_reward(State, Player, Action, Reward)   % from MAX perspective
%   terminal(State, Value)                       % final utility from MAX perspective
%   evaluate(State, Value)                       % heuristic utility if depth hits 0

:- use_module(library(lists)).
:- [f1_env].   % f1_env loads f1_rules and drivers

:- discontiguous minimax/5, minimax_best/4, choose_best/3, max_pair/3, min_pair/3, root_values/4.

other_player(max, min).
other_player(min, max).

% Entry point:
% minimax_best(State, Depth, BestAction, BestValue).
minimax_best(State, Depth, BestAction, BestValue) :-
    minimax(State, Depth, max, BestAction, BestValue).

% Base cases

% Terminal state: return terminal utility
minimax(State, _Depth, _Player, none, Value) :-
    terminal(State, Value),
    !.

% Depth limit reached: return heuristic evaluation
minimax(State, 0, _Player, none, Value) :-
    evaluate(State, Value),
    !.

% No legal actions: evaluate
minimax(State, _Depth, Player, none, Value) :-
    legal_actions(State, Player, Actions),
    Actions == [],
    evaluate(State, Value),
    !.

% Recursive minimax
minimax(State, Depth, Player, BestAction, BestValue) :-
    Depth > 0,
    legal_actions(State, Player, Actions),
    Actions \= [],
    NextDepth is Depth - 1,

    % Evaluate each action into an action-value pair
    findall(action_value(Action, Value),
        (
            member(Action, Actions),
            apply_action(State, Player, Action, NextState),
            step_reward(State, Player, Action, R),
            other_player(Player, NextPlayer),
            minimax(NextState, NextDepth, NextPlayer, _A2, V2),
            Value is R + V2
        ),
        Pairs),

    choose_best(Player, Pairs, action_value(BestAction, BestValue)),
    !.

% Choose best action depending on player
% MAX wants the highest Value, MIN wants the lowest Value.
choose_best(max, [H|T], Best) :-
    foldl(max_pair, T, H, Best).

choose_best(min, [H|T], Best) :-
    foldl(min_pair, T, H, Best).

max_pair(action_value(A1,V1), action_value(A2,V2), action_value(A1,V1)) :-
    V1 >= V2,
    !.
max_pair(_X, Y, Y).

min_pair(action_value(A1,V1), action_value(A2,V2), action_value(A1,V1)) :-
    V1 =< V2,
    !.
min_pair(_X, Y, Y).

% Convenience query for debugging:
% prints each action and its minimax value at the root
root_values(State, Depth, Player, Pairs) :-
    legal_actions(State, Player, Actions),
    NextDepth is Depth - 1,
    findall(action_value(Action, Value),
        (
            member(Action, Actions),
            apply_action(State, Player, Action, NextState),
            step_reward(State, Player, Action, R),
            other_player(Player, NextPlayer),
            minimax(NextState, NextDepth, NextPlayer, _A2, V2),
            Value is R + V2
        ),
        Pairs).