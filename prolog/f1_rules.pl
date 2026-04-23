% prolog/f1_rules.pl
% Interlagos rules + scoring. Driver effects now influence:
% - pace (aggression)
% - tyre degradation (smoothness + aggression + kerb use + optional risk in low grip)
% - plank wear (kerb use + aggression)
% - risk penalty (risk tolerance)

:- ['f1_drivers.pl'].

:- dynamic current_track/1, current_forecast/1.
:- dynamic setup/3.

% Defaults (Python can override with retractall/assertz)
current_track(interlagos).
current_forecast(unstable).

% track(+Track)
track(interlagos).

% forecast_regime(+Regime)
forecast_regime(stable).
forecast_regime(unstable).

% weather_state(+Weather)
weather_state(dry).
weather_state(drizzle).
weather_state(wet).

% transition_prob(+Track, +Regime, +CurrentWeather, +NextWeather, -Probability)
% Markov transitions (example values)
transition_prob(interlagos, stable,   dry,     dry,     0.85).
transition_prob(interlagos, stable,   dry,     drizzle, 0.15).
transition_prob(interlagos, stable,   dry,     wet,     0.00).

transition_prob(interlagos, stable,   drizzle, dry,     0.25).
transition_prob(interlagos, stable,   drizzle, drizzle, 0.55).
transition_prob(interlagos, stable,   drizzle, wet,     0.20).

transition_prob(interlagos, stable,   wet,     dry,     0.10).
transition_prob(interlagos, stable,   wet,     drizzle, 0.55).
transition_prob(interlagos, stable,   wet,     wet,     0.35).

transition_prob(interlagos, unstable, dry,     dry,     0.70).
transition_prob(interlagos, unstable, dry,     drizzle, 0.25).
transition_prob(interlagos, unstable, dry,     wet,     0.05).

transition_prob(interlagos, unstable, drizzle, dry,     0.20).
transition_prob(interlagos, unstable, drizzle, drizzle, 0.50).
transition_prob(interlagos, unstable, drizzle, wet,     0.30).

transition_prob(interlagos, unstable, wet,     dry,     0.05).
transition_prob(interlagos, unstable, wet,     drizzle, 0.40).
transition_prob(interlagos, unstable, wet,     wet,     0.55).

% dry_tyre(+Tyre)
dry_tyre(soft).
dry_tyre(medium).
dry_tyre(hard).

% wet_tyre(+Tyre)
wet_tyre(inter).
wet_tyre(wet).

% slick(+Tyre)
slick(T) :- dry_tyre(T).

% tyre_kind(+Tyre, -Kind)
tyre_kind(T, slick) :- slick(T), !.
tyre_kind(inter, inter) :- !.
tyre_kind(wet, wet).

% front_wing_level(+Level)
front_wing_level(1). front_wing_level(2). front_wing_level(3). front_wing_level(4). front_wing_level(5).

% rear_wing_level(+Level)
rear_wing_level(1).  rear_wing_level(2).  rear_wing_level(3).  rear_wing_level(4).  rear_wing_level(5).

% ride_height_tier(+Tier)
ride_height_tier(low). ride_height_tier(med). ride_height_tier(high).

% front_wing_legal_min(-Min)
front_wing_legal_min(1).

% front_wing_legal_max(-Max)
front_wing_legal_max(5).

% rear_wing_legal_min(-Min)
rear_wing_legal_min(1).

% rear_wing_legal_max(-Max)
rear_wing_legal_max(5).

% ride_height_legal(+RideHeight)
ride_height_legal(low).
ride_height_legal(med).
ride_height_legal(high).

% legal_setup(+FrontWing, +RearWing, +RideHeight)
legal_setup(FW, RW, RH) :-
    front_wing_level(FW),
    rear_wing_level(RW),
    ride_height_tier(RH),
    front_wing_legal_min(FMin), front_wing_legal_max(FMax),
    rear_wing_legal_min(RMin),  rear_wing_legal_max(RMax),
    FW >= FMin, FW =< FMax,
    RW >= RMin, RW =< RMax,
    ride_height_legal(RH).

% setup(+FrontWing, +RearWing, +RideHeight)
% Default setup if Python doesn't set it
setup(3,3,med).

% plank_limit(-LimitValue)
plank_limit(1.0).

% bumpiness(+Track, -BumpinessLevel)
bumpiness(interlagos, med).

% base_plank_wear_per_lap(+RideHeight, -DeltaPerLap)
base_plank_wear_per_lap(low,  0.030).
base_plank_wear_per_lap(med,  0.015).
base_plank_wear_per_lap(high, 0.008).

% bumpiness_mult(+Level, -Multiplier)
bumpiness_mult(low,  1.0).
bumpiness_mult(med,  1.0).
bumpiness_mult(high, 1.2).

% plank_wear_mult(+Tyre, -Multiplier)
% Softer tyres lead to more grip and slightly more plank wear.
plank_wear_mult(soft,   1.15).
plank_wear_mult(medium, 1.10).
plank_wear_mult(hard,   1.05).
plank_wear_mult(inter,  1.02).
plank_wear_mult(wet,    1.01).

% plank_wear_delta(+Track, +RideHeightTier, -DeltaPerLap)
% Considers kerb_use and aggression via current_* helpers.
plank_wear_delta(Track, RH, Delta) :-
    base_plank_wear_per_lap(RH, Base),
    bumpiness(Track, B),
    bumpiness_mult(B, BMult),
    current_plank_mult(KerbMult),
    current_aggr_plank_mult(AggMult),
    Delta is Base * BMult * KerbMult * AggMult.

% update_plank_wear(+CurrentWear, +DeltaPerLap, +Laps, -NewWear)
update_plank_wear(W0, Delta, Laps, W1) :-
    W1 is W0 + Delta * Laps.

% plank_status(+WearValue, -Status)
plank_status(W, safe)     :- plank_limit(L), W =< 0.6*L, !.
plank_status(W, warn)     :- plank_limit(L), W =< 0.9*L, !.
plank_status(W, critical) :- plank_limit(L), W =< L,     !.
plank_status(W, illegal)  :- plank_limit(L), W >  L.

% base_lap_time(+Track, -BaseSeconds)
base_lap_time(interlagos, 90.0).

% downforce_level(+FrontWing, +RearWing, -Level)
downforce_level(FW, RW, low) :- FW + RW =< 4, !.
downforce_level(FW, RW, med) :- FW + RW =< 7, !.
downforce_level(_FW,_RW, high).

% drag_level(+FrontWing, +RearWing, -Level)
drag_level(FW, RW, low) :- FW + RW =< 4, !.
drag_level(FW, RW, med) :- FW + RW =< 7, !.
drag_level(_FW,_RW, high).

% drag_penalty(+DragLevel, -PenaltySeconds)
drag_penalty(low,  0.0).
drag_penalty(med,  0.4).
drag_penalty(high, 0.9).

% wet_downforce_bonus(+DownforceLevel, -BonusSeconds)
wet_downforce_bonus(low,  1.2).
wet_downforce_bonus(med,  0.6).
wet_downforce_bonus(high, 0.0).

% wet_bonus_term(+Weather, +Downforce, -Adjustment)
wet_bonus_term(dry, _DF, 0.0) :- !.
wet_bonus_term(drizzle, DF, Adj) :- wet_downforce_bonus(DF, Adj), !.
wet_bonus_term(wet, DF, Adj) :- wet_downforce_bonus(DF, Adj).

% ride_height_pace_adjust(+RideHeight, -PaceAdjust)
ride_height_pace_adjust(low,  -0.3).
ride_height_pace_adjust(med,   0.0).
ride_height_pace_adjust(high,  0.4).

% age_bucket(+Age, -AgeBucket)
age_bucket(0, fresh).
age_bucket(A, ok)   :- A >= 1, A =< 8, !.
age_bucket(A, old)  :- A >= 9.

% deg_penalty(+Tyre, +AgeBucket, -DegradationPenalty)
deg_penalty(soft,   fresh, 0.2).
deg_penalty(soft,   ok,    0.9).
deg_penalty(soft,   old,   2.2).

deg_penalty(medium, fresh, 0.1).
deg_penalty(medium, ok,    0.6).
deg_penalty(medium, old,   1.5).

deg_penalty(hard,   fresh, 0.1).
deg_penalty(hard,   ok,    0.4).
deg_penalty(hard,   old,   1.0).

deg_penalty(inter,  fresh, 0.2).
deg_penalty(inter,  ok,    0.6).
deg_penalty(inter,  old,   1.4).

deg_penalty(wet,    fresh, 0.3).
deg_penalty(wet,    ok,    0.7).
deg_penalty(wet,    old,   1.6).

% warmup_penalty(+Tyre, -PenaltySeconds)
warmup_penalty(soft,   0.6).
warmup_penalty(medium, 0.8).
warmup_penalty(hard,   1.1).
warmup_penalty(inter,  0.9).
warmup_penalty(wet,    1.0).

% wrong_tyre_penalty(+Weather, +TyreKind, -PenaltySeconds)
% Tyre-weather mismatch (fitness) penalty.
wrong_tyre_penalty(dry, slick,   0.0) :- !.
wrong_tyre_penalty(dry, inter,   2.0) :- !.
wrong_tyre_penalty(dry, wet,     5.0) :- !.

wrong_tyre_penalty(drizzle, slick, 2.5) :- !.
wrong_tyre_penalty(drizzle, inter, 0.8) :- !.
wrong_tyre_penalty(drizzle, wet,   3.0) :- !.

wrong_tyre_penalty(wet, slick,   20.0) :- !.
wrong_tyre_penalty(wet, inter,    1.0) :- !.
wrong_tyre_penalty(wet, wet,      0.0) :- !.

% crash_risk_penalty_scaled(+Weather, +Tyre, +Downforce, +RiskMultiplier, -PenaltySeconds)
% Applies crash-risk penalty scaled by driver risk tolerance.
crash_risk_penalty_scaled(dry, _Tyre, _DF, _RiskMult, 0.0) :- !.
crash_risk_penalty_scaled(drizzle, Tyre, DF, RiskMult, Pen) :-
    tyre_kind(Tyre, Kind),
    base_risk_drizzle(Kind, DF, Base),
    Pen is Base * RiskMult, !.
crash_risk_penalty_scaled(wet, Tyre, DF, RiskMult, Pen) :-
    tyre_kind(Tyre, Kind),
    base_risk_wet(Kind, DF, Base),
    Pen is Base * RiskMult.

% base_risk_drizzle(+TyreKind, +Downforce, -BaseRisk)
base_risk_drizzle(slick, low,  6.0).
base_risk_drizzle(slick, med,  4.0).
base_risk_drizzle(slick, high, 2.5).
base_risk_drizzle(inter, _DF,  1.0).
base_risk_drizzle(wet,   _DF,  1.2).

% base_risk_wet(+TyreKind, +Downforce, -BaseRisk)
base_risk_wet(slick, low,  25.0).
base_risk_wet(slick, med,  18.0).
base_risk_wet(slick, high, 12.0).
base_risk_wet(inter, _DF,   2.0).
base_risk_wet(wet,   _DF,   0.8).

% low_grip_weather(+Weather)
% OPTIONAL: extra degradation when low grip (drizzle/wet), scaled by risk tolerance.
% This makes "riskier" drivers cook tyres more when conditions are sketchy.
low_grip_weather(drizzle).
low_grip_weather(wet).

% weather_deg_factor(+Weather, -DegradationFactor)
weather_deg_factor(Weather, F) :-
    ( low_grip_weather(Weather) -> current_risk_deg_mult(F)
    ; F = 1.0 ).

% lap_cost(+Track, +Weather, +Tyre, +Age, +WarmupFlag, +FrontWing, +RearWing, +RideHeight, -Cost)
% Computes total lap time cost combining all factors: pace, drag, wet bonus, deg, risk, warmup.
lap_cost(Track, Weather, Tyre, Age, WarmupFlag, FW, RW, RH, Cost) :-
    base_lap_time(Track, Base),

    current_pace_bonus(PaceAdj),
    current_deg_mult(SmoothDeg),
    current_aggr_deg_mult(AggDeg),
    current_kerb_deg_mult(KerbDeg),
    weather_deg_factor(Weather, WeatherDeg),

    current_risk_mult(RiskMult),

    downforce_level(FW, RW, DF),
    drag_level(FW, RW, Drag),
    drag_penalty(Drag, DragPen),

    wet_bonus_term(Weather, DF, WetAdj),

    age_bucket(Age, AB),
    deg_penalty(Tyre, AB, Deg0),

    % FINAL tyre deg multiplier: smoothness * aggression * kerb use * (optional weather/risk)
    DegPen is Deg0 * SmoothDeg * AggDeg * KerbDeg * WeatherDeg,

    tyre_kind(Tyre, Kind),
    wrong_tyre_penalty(Weather, Kind, WrongPen),

    crash_risk_penalty_scaled(Weather, Tyre, DF, RiskMult, RiskPen),

    ( WarmupFlag =:= 1 -> warmup_penalty(Tyre, WUP) ; WUP = 0.0 ),

    ride_height_pace_adjust(RH, RHAdj),

    Cost is Base + PaceAdj + DragPen + WetAdj + DegPen + WrongPen + RiskPen + WUP + RHAdj.

% pit_loss(+Track, -PitStopSeconds)
pit_loss(interlagos, 20.0).

% used_two_dry(+UsedList)
% Checks if at least two distinct dry compound tyres have been used.
used_two_dry(Used) :-
    findall(T, (member(T, Used), dry_tyre(T)), DryUsed),
    sort(DryUsed, Unique),
    length(Unique, N),
    N >= 2.

% opponent_policy(+Weather, +Tyre, +AgeBucket, -RecommendedAction)
% Simple opponent policy hook (can be used for fixed opponent behavior).
opponent_policy(wet, _Tyre, _AgeB, pit(inter)) :- !.
opponent_policy(drizzle, Tyre, old, pit(inter)) :- slick(Tyre), !.
opponent_policy(dry, _Tyre, old, pit(medium)) :- !.
opponent_policy(_, _Tyre, _AgeB, stay).