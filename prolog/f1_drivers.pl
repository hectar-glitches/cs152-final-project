% prolog/f1_drivers.pl
% Driver roster + traits + trait->multiplier mappings.
% f1_rules.pl calls the "current_*" helpers here.

:- dynamic current_driver/1.
:- dynamic driver/1, aggression/2, smoothness/2, kerb_use/2, risk_tolerance/2.

% Suppress "not together in source-file" warnings (you can also reorder facts instead)
:- discontiguous driver/1.
:- discontiguous aggression/2.
:- discontiguous smoothness/2.
:- discontiguous kerb_use/2.
:- discontiguous risk_tolerance/2.

% Pick active driver (Python can retract/assert this)
current_driver(max).


% Driver trait facts

driver(max).
aggression(max, high).
smoothness(max, low).
kerb_use(max, high).
risk_tolerance(max, high).

driver(lewis).
aggression(lewis, med).
smoothness(lewis, high).
kerb_use(lewis, low).
risk_tolerance(lewis, med).

driver(lando).
aggression(lando, med).
smoothness(lando, med).
kerb_use(lando, med).
risk_tolerance(lando, med).

driver(charles).
aggression(charles, high).
smoothness(charles, med).
kerb_use(charles, med).
risk_tolerance(charles, high).

driver(george).
aggression(george, med).
smoothness(george, med).
kerb_use(george, med).
risk_tolerance(george, med).


% Trait -> effect tables


% Pace bonus (seconds per lap): negative means faster
pace_bonus(low,  0.3).
pace_bonus(med,  0.0).
pace_bonus(high, -0.6).

% Base tyre degradation multiplier from smoothness (higher = more deg)
% (You can tune these)
smoothness_mult(high, 1.05).
smoothness_mult(med,  1.35).
smoothness_mult(low,  1.75).

% Extra tyre degradation multiplier from aggression (pushing heats tyres)
aggression_deg_mult(low,  1.00).
aggression_deg_mult(med,  1.10).
aggression_deg_mult(high, 1.25).

% Extra tyre degradation multiplier from kerb usage (snap loads / traction events)
kerb_deg_mult(low,  1.00).
kerb_deg_mult(med,  1.06).
kerb_deg_mult(high, 1.12).

% Plank wear multiplier from kerb usage (existing idea)
kerb_plank_mult(low,  0.95).
kerb_plank_mult(med,  1.05).
kerb_plank_mult(high, 1.15).

% Extra plank wear multiplier from aggression (attacking kerbs / lower margin)
aggression_plank_mult(low,  1.00).
aggression_plank_mult(med,  1.05).
aggression_plank_mult(high, 1.12).

% Risk multiplier for "risk penalty" term in drizzle/wet (bigger = more penalty)
risk_mult(low,  0.80).
risk_mult(med,  1.05).
risk_mult(high, 1.25).

% Optional: risk can also amplify tyre deg ONLY in low-grip (drizzle/wet),
% representing wheelspin / sliding when driving "on the edge".
risk_deg_mult(low,  1.00).
risk_deg_mult(med,  1.05).
risk_deg_mult(high, 1.12).


% Current-driver helpers


current_pace_bonus(B) :-
    current_driver(D),
    aggression(D, A),
    pace_bonus(A, B).

current_deg_mult(M) :-
    current_driver(D),
    smoothness(D, S),
    smoothness_mult(S, M).

current_aggr_deg_mult(M) :-
    current_driver(D),
    aggression(D, A),
    aggression_deg_mult(A, M).

current_kerb_deg_mult(M) :-
    current_driver(D),
    kerb_use(D, K),
    kerb_deg_mult(K, M).

current_plank_mult(M) :-
    current_driver(D),
    kerb_use(D, K),
    kerb_plank_mult(K, M).

current_aggr_plank_mult(M) :-
    current_driver(D),
    aggression(D, A),
    aggression_plank_mult(A, M).

current_risk_mult(M) :-
    current_driver(D),
    risk_tolerance(D, R),
    risk_mult(R, M).

current_risk_deg_mult(M) :-
    current_driver(D),
    risk_tolerance(D, R),
    risk_deg_mult(R, M).