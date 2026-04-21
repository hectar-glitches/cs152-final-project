% f1_rules.pl
% Domain knowledge, constraints, and scoring components for Interlagos.
% Used by f1_env.pl and f1_minimax.pl
%
% Key ideas:
%   - Weather is discrete: dry / drizzle / wet
%   - Forecast regime selects transition probabilities (Python can sample)
%   - Setup is fixed at race start: wing levels + ride height
%   - Plank wear accumulates; exceeding the limit leads to DSQ (terminal)
%   - Tyre choice interacts with weather via penalties
%       (slick "gamble" in drizzle is allowed but slower/riskier)
%   - Driver profile affects wear/risk multipliers

% Consult drivers.pl for driver traits and derived helpers
:- ['f1_drivers.pl'].

:- dynamic current_track/1, current_forecast/1.
:- dynamic setup/3.  % setup(FrontWing, RearWing, RideHeightTier)
% Track and weather
:- discontiguous current_track/1, forecast_regime/1, weather_state/1, transition_prob/5, setup/3, legal_setup/3.
:- discontiguous plank_delta_player/3, lap_cost_player/9, set_weather/3.
:- discontiguous used_two_dry/1, opponent_policy/4.
:- discontiguous wet_bonus_term/3, ride_height_pace_adjust/2.
:- discontiguous base_lap_time/2, downforce_level/3, drag_level/3, drag_penalty/2, wet_downforce_bonus/2.
:- discontiguous age_bucket/2, deg_penalty/3, warmup_penalty/2, wrong_tyre_penalty/3, crash_risk_penalty_scaled/5.

current_track(interlagos).

forecast_regime(stable).
forecast_regime(unstable).

weather_state(dry).
weather_state(drizzle).
weather_state(wet).

% transition_prob(+Track, +ForecastRegime, +CurrentWeather, +NextWeather, -Prob)
% Transition probabilities are tunable; current values are illustrative.
transition_prob(interlagos, stable, dry,     dry,     0.85).
transition_prob(interlagos, stable, dry,     drizzle, 0.15).
transition_prob(interlagos, stable, dry,     wet,     0.00).

transition_prob(interlagos, stable, drizzle, dry,     0.25).
transition_prob(interlagos, stable, drizzle, drizzle, 0.55).
transition_prob(interlagos, stable, drizzle, wet,     0.20).

transition_prob(interlagos, stable, wet,     dry,     0.10).
transition_prob(interlagos, stable, wet,     drizzle, 0.55).
transition_prob(interlagos, stable, wet,     wet,     0.35).

transition_prob(interlagos, unstable, dry,     dry,     0.70).
transition_prob(interlagos, unstable, dry,     drizzle, 0.25).
transition_prob(interlagos, unstable, dry,     wet,     0.05).

transition_prob(interlagos, unstable, drizzle, dry,     0.20).
transition_prob(interlagos, unstable, drizzle, drizzle, 0.50).
transition_prob(interlagos, unstable, drizzle, wet,     0.30).

transition_prob(interlagos, unstable, wet,     dry,     0.05).
transition_prob(interlagos, unstable, wet,     drizzle, 0.40).
transition_prob(interlagos, unstable, wet,     wet,     0.55).
% Tyres
dry_tyre(soft).
dry_tyre(medium).
dry_tyre(hard).

wet_tyre(inter).
wet_tyre(wet).

slick(T) :- dry_tyre(T).

% tyre_kind(+Tyre, -Kind)  --  collapses all slick compounds to the atom 'slick'
tyre_kind(T,     slick) :- slick(T), !.
tyre_kind(inter, inter) :- !.
tyre_kind(wet,   wet).
% Car setup: wing levels and ride height
front_wing_level(1).
front_wing_level(2).
front_wing_level(3).
front_wing_level(4).
front_wing_level(5).

rear_wing_level(1).
rear_wing_level(2).
rear_wing_level(3).
rear_wing_level(4).
rear_wing_level(5).

ride_height_tier(low).
ride_height_tier(med).
ride_height_tier(high).

front_wing_legal_min(1).
front_wing_legal_max(5).

rear_wing_legal_min(1).
rear_wing_legal_max(5).

ride_height_legal(low).
ride_height_legal(med).
ride_height_legal(high).

% legal_setup(+FW, +RW, +RH)
legal_setup(FW, RW, RH) :-
    front_wing_level(FW),
    rear_wing_level(RW),
    ride_height_tier(RH),
    front_wing_legal_min(FMin),
    front_wing_legal_max(FMax),
    rear_wing_legal_min(RMin),
    rear_wing_legal_max(RMax),
    FW >= FMin, FW =< FMax,
    RW >= RMin, RW =< RMax,
    ride_height_legal(RH).
% Plank wear
% Maximum legal plank wear in mm before DSQ
plank_limit(1.0).

% Track bumpiness level
bumpiness(interlagos, med).

% Base plank wear per lap (mm) by ride height tier
base_plank_wear_per_lap(low,  0.030).
base_plank_wear_per_lap(med,  0.015).
base_plank_wear_per_lap(high, 0.008).

% Multiplier on base wear based on track bumpiness
bumpiness_mult(low,  1.0).
bumpiness_mult(med,  1.0).
bumpiness_mult(high, 1.2).

% plank_wear_delta(+Track, +RideHeightTier, -DeltaPerLap)
plank_wear_delta(Track, RH, Delta) :-
    base_plank_wear_per_lap(RH, Base),
    bumpiness(Track, B),
    bumpiness_mult(B, BMult),
    current_plank_mult(DMult),  % driver-specific multiplier from drivers.pl
    Delta is Base * BMult * DMult.

% update_plank_wear(+W0, +DeltaPerLap, +Laps, -W1)
update_plank_wear(W0, Delta, Laps, W1) :-
    W1 is W0 + Delta * Laps.

% plank_status(+Wear, -Bucket)  --  bucketed for RL state compression
plank_status(W, safe) :-
    plank_limit(L),
    W =< 0.6 * L,
    !.
plank_status(W, warn) :-
    plank_limit(L),
    W =< 0.9 * L,
    !.
plank_status(W, critical) :-
    plank_limit(L),
    W =< L,
    !.
plank_status(W, illegal) :-
    plank_limit(L),
    W > L.
% Aerodynamics
% Base lap time in seconds for this track
base_lap_time(interlagos, 90.0).

% Downforce and drag levels derived from combined wing settings
downforce_level(FW, RW, low)  :- FW + RW =< 4, !.
downforce_level(FW, RW, med)  :- FW + RW =< 7, !.
downforce_level(_,  _,  high).

drag_level(FW, RW, low)  :- FW + RW =< 4, !.
drag_level(FW, RW, med)  :- FW + RW =< 7, !.
drag_level(_,  _,  high).

% Lap time penalty from drag (seconds/lap)
drag_penalty(low,  0.0).
drag_penalty(med,  0.4).
drag_penalty(high, 0.9).

% Lap time saved from downforce in wet/drizzle conditions (seconds/lap)
wet_downforce_bonus(low,  1.2).
wet_downforce_bonus(med,  0.6).
wet_downforce_bonus(high, 0.0).
% Tyre degradation
% age_bucket(+LapsOnTyre, -Bucket)
age_bucket(0, fresh).
age_bucket(A, ok)  :- A >= 1, A =< 8, !.
age_bucket(A, old) :- A >= 9.

% deg_penalty(+Compound, +AgeBucket, -PenaltyPerLap)  --  dry compounds
deg_penalty(soft,   fresh, 0.2).
deg_penalty(soft,   ok,    0.9).
deg_penalty(soft,   old,   2.2).

deg_penalty(medium, fresh, 0.1).
deg_penalty(medium, ok,    0.6).
deg_penalty(medium, old,   1.5).

deg_penalty(hard,   fresh, 0.1).
deg_penalty(hard,   ok,    0.4).
deg_penalty(hard,   old,   1.0).

% Wet compounds degrade differently
deg_penalty(inter, fresh, 0.2).
deg_penalty(inter, ok,    0.6).
deg_penalty(inter, old,   1.4).

deg_penalty(wet,   fresh, 0.3).
deg_penalty(wet,   ok,    0.7).
deg_penalty(wet,   old,   1.6).

% Warm-up penalty on the first lap after a pit stop (seconds)
warmup_penalty(soft,   0.6).
warmup_penalty(medium, 0.8).
warmup_penalty(hard,   1.1).
warmup_penalty(inter,  0.9).
warmup_penalty(wet,    1.0).
% Tyre-weather mismatch
% wrong_tyre_penalty(+Weather, +TyreKind, -Penalty)
% The drizzle/slick case is the "slick gamble": legal but costly.
wrong_tyre_penalty(dry,     slick,  0.0) :- !.
wrong_tyre_penalty(dry,     inter,  2.0) :- !.
wrong_tyre_penalty(dry,     wet,    5.0) :- !.

wrong_tyre_penalty(drizzle, slick,  2.5) :- !.  % gamble zone
wrong_tyre_penalty(drizzle, inter,  0.8) :- !.
wrong_tyre_penalty(drizzle, wet,    3.0) :- !.

wrong_tyre_penalty(wet,     slick, 20.0) :- !.  % extremely bad, but not terminal
wrong_tyre_penalty(wet,     inter,  1.0) :- !.
wrong_tyre_penalty(wet,     wet,    0.0) :- !.
% Crash risk
% crash_risk_penalty_scaled(+Weather, +Tyre, +DownforceLevel, +RiskMult, -Penalty)
% Risk is zero in dry conditions; increases on slicks at low downforce in drizzle/wet.
crash_risk_penalty_scaled(dry,     _,    _,  _,        0.0) :- !.
crash_risk_penalty_scaled(drizzle, Tyre, DF, RiskMult, Pen) :-
    tyre_kind(Tyre, Kind),
    base_risk_drizzle(Kind, DF, Base),
    Pen is Base * RiskMult,
    !.
crash_risk_penalty_scaled(wet,     Tyre, DF, RiskMult, Pen) :-
    tyre_kind(Tyre, Kind),
    base_risk_wet(Kind, DF, Base),
    Pen is Base * RiskMult.

% base_risk_drizzle(+TyreKind, +DownforceLevel, -BaseRisk)
base_risk_drizzle(slick, low,  6.0).
base_risk_drizzle(slick, med,  4.0).
base_risk_drizzle(slick, high, 2.5).
base_risk_drizzle(inter, _,    1.0).
base_risk_drizzle(wet,   _,    1.2).

% base_risk_wet(+TyreKind, +DownforceLevel, -BaseRisk)
base_risk_wet(slick, low,  25.0).
base_risk_wet(slick, med,  18.0).
base_risk_wet(slick, high, 12.0).
base_risk_wet(inter, _,     2.0).
base_risk_wet(wet,   _,     0.8).
% Per-lap cost model
% lap_cost(+Track, +Weather, +Tyre, +AgeInt, +WarmupFlag, +FW, +RW, +RH, -Cost)
lap_cost(Track, Weather, Tyre, Age, WarmupFlag, FW, RW, RH, Cost) :-
    base_lap_time(Track, Base),
    current_pace_bonus(PaceAdj),
    current_deg_mult(DegMult),
    current_risk_mult(RiskMult),
    downforce_level(FW, RW, DF),
    drag_level(FW, RW, Drag),
    drag_penalty(Drag, DragPen),
    wet_bonus_term(Weather, DF, WetAdj),
    age_bucket(Age, AB),
    deg_penalty(Tyre, AB, Deg0),
    DegPen is Deg0 * DegMult,
    tyre_kind(Tyre, Kind),
    wrong_tyre_penalty(Weather, Kind, WrongPen),
    crash_risk_penalty_scaled(Weather, Tyre, DF, RiskMult, RiskPen),
    ( WarmupFlag =:= 1 -> warmup_penalty(Tyre, WUP) ; WUP = 0.0 ),
    ride_height_pace_adjust(RH, RHAdj),
    Cost is Base + PaceAdj + DragPen + WetAdj + DegPen + WrongPen + RiskPen + WUP + RHAdj.

% wet_bonus_term(+Weather, +DownforceLevel, -Adjustment)
wet_bonus_term(dry,     _,  0.0) :- !.
wet_bonus_term(drizzle, DF, Adj) :- wet_downforce_bonus(DF, Adj), !.
wet_bonus_term(wet,     DF, Adj) :- wet_downforce_bonus(DF, Adj).

% Ride height effect on lap time (seconds/lap)
ride_height_pace_adjust(low,  -0.3).
ride_height_pace_adjust(med,   0.0).
ride_height_pace_adjust(high,  0.4).
% Pit stops and strategy
% Time lost in the pit lane (seconds)
pit_loss(interlagos, 20.0).

% used_two_dry(+UsedList)
% Succeeds when at least two distinct dry compounds appear in UsedList.
used_two_dry(Used) :-
    findall(T, (member(T, Used), dry_tyre(T)), DryUsed),
    sort(DryUsed, Unique),
    length(Unique, N),
    N >= 2.
% Opponent policy
% opponent_policy(+Weather, +OppTyre, +OppAgeBucket, -Action)
% Action is either 'stay' or 'pit(Tyre)'.
% Keep the opponent fixed during training for simplicity.
opponent_policy(wet,     _,    _,   pit(inter))  :- !.
opponent_policy(drizzle, Tyre, old, pit(inter))  :- slick(Tyre), !.
opponent_policy(dry,     _,    old, pit(medium)) :- !.
opponent_policy(_,       _,    _,   stay).
