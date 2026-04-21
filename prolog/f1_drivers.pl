% prolog/drivers.pl

:- dynamic current_driver/1.
:- dynamic driver/1.

% Pick the active driver for a run (Python can retract/assert this too)
current_driver(max).

% Driver facts
driver(max).

% Traits (discrete, explainable)
% aggression: affects pace bonus and (optionally) crash risk
aggression(max, high).        % low | med | high

% smoothness: affects tyre degradation
smoothness(high, med, low).         % low | med | high (low = harsher on tyres)

% kerb use: affects plank wear rate
kerb_use(high, med, low).          % low | med | high (high = more aggressive kerb use, more plank wear)

% risk tolerance: affects crash-risk penalty scaling / willingness to gamble
risk_tolerance(high, med, low).    % low | med | high

% Other driver profiles.
% Additional driver facts
driver(lando).
driver(oscar).
driver(lewis).
driver(charles).
driver(george).
driver(fernando).
driver(carlos).
driver(alex).
driver(kimi).
driver(nico).

% Lando Norris
% Fast, assertive when needed, but generally cleaner on tyres than outright "wild"
aggression(lando, med).
smoothness(lando, med).
kerb_use(lando, med).
risk_tolerance(lando, med).

% Oscar Piastri
% Calm, measured, strong tyre management
aggression(oscar, med).
smoothness(oscar, med).
kerb_use(oscar, med).
risk_tolerance(oscar, med).

% Lewis Hamilton
% Excellent tyre preservation, usually measured risk, still capable of aggressive racecraft
aggression(lewis, med).
smoothness(lewis, high).
kerb_use(lewis, low).
risk_tolerance(lewis, med).

% Charles Leclerc
% Quick and committed, willing to take bold options
aggression(charles, high).
smoothness(charles, med).
kerb_use(charles, med).
risk_tolerance(charles, high).

% George Russell
% Precise, usually controlled, moderately aggressive
aggression(george, med).
smoothness(george, med).
kerb_use(george, med).
risk_tolerance(george, med).

% Fernando Alonso
% Very racecraft-heavy, opportunistic, usually excellent on tyres
aggression(fernando, high).
smoothness(fernando, high).
kerb_use(fernando, low).
risk_tolerance(fernando, med).

% Carlos Sainz
% Methodical, tidy, usually kind to tyres
aggression(carlos, med).
smoothness(carlos, high).
kerb_use(carlos, low).
risk_tolerance(carlos, med).

% Alex Albon
% Generally controlled, adaptable, not excessively risky
aggression(alex, med).
smoothness(alex, high).
kerb_use(alex, low).
risk_tolerance(alex, med).

% Kimi Antonelli
% High ceiling, still more willing to lean into risk as a younger driver
aggression(kimi, high).
smoothness(kimi, med).
kerb_use(kimi, med).
risk_tolerance(kimi, high).

% Nico Hulkenberg
% Experienced, stable, usually lower-risk and mechanically sympathetic
aggression(nico, med).
smoothness(nico, high).
kerb_use(nico, low).
risk_tolerance(nico, low).

% Trait to multiplier mappings
% (Used by f1_rules.pl)

% Pace bonus (seconds per lap): negative means faster
pace_bonus(low,  0.3).
pace_bonus(med,  0.0).
pace_bonus(high, -0.6).

% Degradation multiplier: higher = tyres degrade faster
smoothness_mult(high, 0.9).
smoothness_mult(med,  1.05).
smoothness_mult(low,  1.1).

% Plank wear multiplier: higher = more plank wear per lap
kerb_mult(low,  0.95).
kerb_mult(med, 1.05).
kerb_mult(high, 1.15).

% Crash-risk multiplier: higher = more risk penalty in drizzle/wet (or bigger crash chance if you model it that way)
risk_mult(low,  0.8).
risk_mult(med,  1.05).
risk_mult(high, 1.25).


% Derived “current driver” helpers
% (Call these from f1_rules.pl)

current_pace_bonus(B) :-
    current_driver(D),
    aggression(D, A),
    pace_bonus(A, B).

current_deg_mult(M) :-
    current_driver(D),
    smoothness(D, S),
    smoothness_mult(S, M).

current_plank_mult(M) :-
    current_driver(D),
    kerb_use(D, K),
    kerb_mult(K, M).

current_risk_mult(M) :-
    current_driver(D),
    risk_tolerance(D, R),
    risk_mult(R, M).