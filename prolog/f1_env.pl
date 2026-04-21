% prolog/f1_env.pl
% Environment interface used by:
%  - Q-learning (Python via PySWIP)
%  - Minimax (Prolog)
% State is fully Markov and includes cumulative times so minimax is clean:
%
% state(
%   LapsLeft,
%   Weather,                 % dry|drizzle|wet
%   my(Tyre, Age, UsedList, PlankWear, WarmFlag, Time),
%   opp(Tyre, Age, UsedList, PlankWear, WarmFlag, Time)
% ).
%
% Action format:
%   stay
%   pit(Tyre)   where Tyre is soft|medium|hard|inter|wet
%
% Reward is from MAX perspective (utility = OppTime - MyTime):
%   - If MAX acts: reward = -my_step_cost
%   - If MIN acts: reward = +opp_step_cost

:- use_module(library(lists)).
:- [f1_rules].

:- discontiguous apply_action/4, step_cost/4, legal_actions/3, step_reward/4, terminal/2, evaluate/2.
:- discontiguous car_fields/6, rebuild_car/8, next_tyre_age_warm/7, update_used/3, pit_cost/2.
:- discontiguous get_setup/3, plank_delta_player/3, lap_cost_player/9, set_weather/3, init_state/5.

% Helpers: tyre sets
all_tyre(soft).
all_tyre(medium).
all_tyre(hard).
all_tyre(inter).
all_tyre(wet).

% Decision interface
% legal_actions(+State, +Player, -Actions)
% Player is max|min
legal_actions(state(L, _W, _My, _Opp), _Player, Actions) :-
    L =< 0,
    Actions = [],
    !.
legal_actions(State, _Player, []) :-
    terminal(State, _Value),
    !.
legal_actions(_State, _Player, Actions) :-
    % Always allow stay and any pit choice (you can restrict if you want)
    findall(pit(T), all_tyre(T), PitActions),
    Actions = [stay|PitActions].

% apply_action(+State, +Player, +Action, -NextState)
% Updates:
%  - laps_left decreases by 1
%  - chosen player's tyre/age/used/warmflag/time
%  - plank wear increases for chosen player
% Weather is held constant here; Python can update Weather stochastically between steps.
apply_action(state(L, W, My0, Opp0), Player, Action,
             state(L2, W, My1, Opp1)) :-
    L > 0,
    L2 is L - 1,
    ( Player == max ->
        step_car(max, W, Action, My0, My1),
        Opp1 = Opp0
    ; Player == min ->
        step_car(min, W, Action, Opp0, Opp1),
        My1 = My0
    ).

% step_reward(+State, +Player, +Action, -Reward)
% Reward is from MAX perspective (OppTime - MyTime).
% So:
%  - MAX action increases MyTime => reward is negative
%  - MIN action increases OppTime => reward is positive
step_reward(State, Player, Action, Reward) :-
    utility(State, U0),
    apply_action(State, Player, Action, NextState),
    utility(NextState, U1),
    Reward is U1 - U0.

utility(state(_L,_W,
              my(_T1,_A1,_U1,_PW1,_WF1,TimeMy),
              opp(_T2,_A2,_U2,_PW2,_WF2,TimeOpp)), U) :-
    U is TimeOpp - TimeMy.

% step_cost(+State, +Player, +Action, -Cost)
% Computes one-step cost for the acting player:
%   lap_cost + (pit_loss if pitting)
% This uses:
%   - lap_cost_player/7 wrapper to apply driver multipliers differently for MAX vs MIN.
step_cost(state(_L, W, My, Opp), Player, Action, Cost) :-
    get_setup(FW, RW, RH),
    ( Player == max ->
        car_fields(My, Tyre0, Age0, _Used, Warm0, _Time),
        next_tyre_age_warm(Action, Tyre0, Age0, Warm0, Tyre1, Age1, Warm1),
        lap_cost_player(max, W, Tyre1, Age1, Warm1, FW, RW, RH, LapCost),
        pit_cost(Action, PitCost),
        Cost is LapCost + PitCost
    ; Player == min ->
        car_fields(Opp, Tyre0, Age0, _Used, Warm0, _Time),
        next_tyre_age_warm(Action, Tyre0, Age0, Warm0, Tyre1, Age1, Warm1),
        lap_cost_player(min, W, Tyre1, Age1, Warm1, FW, RW, RH, LapCost),
        pit_cost(Action, PitCost),
        Cost is LapCost + PitCost
    ).

debug_one(State, Player, Action) :-
    ( apply_action(State, Player, Action, NS) ->
        writeln(applied=NS),
        step_reward(State, Player, Action, R),
        writeln(reward=R)
    ; writeln('apply_action FAILED')
    ).

debug_action(State, Player, Action) :-
    ( apply_action(State, Player, Action, NextState) ->
        writeln('apply_action OK'),
        writeln(next_state=NextState),
        ( step_reward(State, Player, Action, R) ->
            writeln('step_reward OK'),
            writeln(reward=R)
        ;   writeln('step_reward FAILED')
        )
    ; writeln('apply_action FAILED')
    ).

% terminal(+State, -Value)
% Terminal if:
%   - plank illegal for either player (DSQ)
%   - laps_left == 0 (race end)
%
% Value is from MAX perspective: OppTime - MyTime, with big DSQ penalties.
terminal(state(_L, _W, my(_T1,_A1,_U1, PW1,_WF1,TimeMy),
                  opp(_T2,_A2,_U2, PW2,_WF2,TimeOpp)), Value) :-
    plank_status(PW1, illegal),
    % MAX DSQ => huge negative
    Value is -1000 - (TimeMy - TimeOpp),
    !.
terminal(state(_L, _W, my(_T1,_A1,_U1, PW1,_WF1,TimeMy),
                  opp(_T2,_A2,_U2, PW2,_WF2,TimeOpp)), Value) :-
    plank_status(PW2, illegal),
    % MIN DSQ => huge positive
    Value is 1000 + (TimeOpp - TimeMy),
    !.
terminal(state(L, W,
              my(_TyMy,_AgeMy,UsedMy,_PWMy,_WFMy,TimeMy),
              opp(_TyOp,_AgeOp,UsedOp,_PWOp,_WFOp,TimeOpp)), Value) :-
    L =< 0,
    % End of horizon: base utility = OppTime - MyTime
    Base is TimeOpp - TimeMy,
    % Apply tyre rule penalty if you want:
    % If race ends and it's "dry-enough", enforce 2 dry compounds for each.
    end_rule_penalty(W, UsedMy, UsedOp, Pen),
    Value is Base + Pen,
    !.

% Rule penalty: if Weather ends as dry or drizzle, enforce 2 dry compounds.
end_rule_penalty(W, UsedMy, UsedOp, Pen) :-
    ( W == wet ->
        Pen is 0
    ; % dry or drizzle
      ( used_two_dry(UsedMy) -> PMy = 0 ; PMy = -500 ),
      ( used_two_dry(UsedOp) -> POp = 0 ; POp = +500 ), % if opponent fails, helps MAX
      Pen is PMy + POp
    ).

% evaluate(+State, -Value)
% Used by minimax at Depth=0 when not terminal.
% Simple heuristic: current OppTime - MyTime (can add extra shaping if you want)
evaluate(state(_L, _W,
              my(_TyMy,_AgeMy,_UsedMy,_PWMy,_WFMy,TimeMy),
              opp(_TyOp,_AgeOp,_UsedOp,_PWOp,_WFOp,TimeOpp)), Value) :-
    Value is TimeOpp - TimeMy.

% Internal: stepping a car

% step_car(+Player, +Weather, +Action, +Car0, -Car1)
% Car term is my(...) or opp(...). We keep the functor the same as input.
step_car(Player, Weather, Action,
         Car0,
         Car1) :-

    car_fields(Car0, Tyre0, Age0, Used0, PW0, Warm0, Time0),
    next_tyre_age_warm(Action, Tyre0, Age0, Warm0, Tyre1, Age1, Warm1),
    update_used(Action, Used0, Used1),

    current_track(Track),
    get_setup(_FW,_RW,RH),
    plank_delta_player(Player, Track, RH, Delta),
    update_plank_wear(PW0, Delta, 1, PW1),

    get_setup(FW, RW, RH2),
    lap_cost_player(Player, Weather, Tyre1, Age1, Warm1, FW, RW, RH2, LapCost),
    pit_cost(Action, PitCost),
    Time1 is Time0 + LapCost + PitCost,

    rebuild_car(Car0, Tyre1, Age1, Used1, PW1, Warm1, Time1, Car1).

% car_fields(+CarTerm, -Tyre, -Age, -Used, -Plank, -Warm, -Time)
car_fields(my(T,A,U,PW,Wf,Time),  T,A,U,PW,Wf,Time).
car_fields(opp(T,A,U,PW,Wf,Time), T,A,U,PW,Wf,Time).

% rebuild_car(+OldCarTerm, +Tyre,+Age,+Used,+PW,+Warm,+Time, -NewCarTerm)
rebuild_car(my(_,_,_,_,_,_),  T,A,U,PW,Wf,Time, my(T,A,U,PW,Wf,Time)).
rebuild_car(opp(_,_,_,_,_,_), T,A,U,PW,Wf,Time, opp(T,A,U,PW,Wf,Time)).


% In State we store my(...) and opp(...), but in step_car we store car(...)
% That’s just an internal convenience.

car_to_my(car(T,A,U,PW,Wf,Time), my(T,A,U,PW,Wf,Time)).
car_to_opp(car(T,A,U,PW,Wf,Time), opp(T,A,U,PW,Wf,Time)).
my_to_car(my(T,A,U,PW,Wf,Time), car(T,A,U,PW,Wf,Time)).
opp_to_car(opp(T,A,U,PW,Wf,Time), car(T,A,U,PW,Wf,Time)).

% next_tyre_age_warm(Action, Tyre0, Age0, Warm0, Tyre1, Age1, Warm1)
next_tyre_age_warm(stay, Tyre, Age0, _Warm0, Tyre, Age1, 0) :-
    Age1 is Age0 + 1.
next_tyre_age_warm(pit(NewTyre), _Tyre0, _Age0, _Warm0, NewTyre, 0, 1).

% update_used(Action, Used0, Used1)
update_used(stay, Used, Used).
update_used(pit(T), Used0, Used1) :-
    ( member(T, Used0) -> Used1 = Used0 ; Used1 = [T|Used0] ).

% pit_cost(Action, Cost)
pit_cost(stay, 0.0).
pit_cost(pit(_), Cost) :-
    current_track(Track),
    pit_loss(Track, Cost).

% Setup access
% setup/3 is dynamic and should be asserted once per run:
%   setup(FW, RW, RH).
get_setup(FW, RW, RH) :-
    setup(FW, RW, RH), !.
get_setup(3, 3, med).  % default if not set

% plank_delta_player(Player, Track, RH, Delta)
% MAX uses current_driver multipliers from drivers.pl
% MIN uses "neutral" multipliers (equivalent to balanced driver)
plank_delta_player(max, Track, RH, Delta) :-
    plank_wear_delta(Track, RH, Delta).

plank_delta_player(min, Track, RH, Delta) :-
    % Neutral opponent plank mult = 1.0 (balanced baseline)
    base_plank_wear_per_lap(RH, Base),
    bumpiness(Track, B),
    bumpiness_mult(B, BMult),
    Delta is Base * BMult * 1.0.

% lap_cost_player(Player, Weather, Tyre, Age, WarmFlag, FW, RW, RH, Cost)
% MAX uses current driver multipliers from drivers.pl via lap_cost/9 in f1_rules.pl
% MIN uses neutral multipliers (balanced baseline) implemented here.
lap_cost_player(max, Weather, Tyre, Age, WarmFlag, FW, RW, RH, Cost) :-
    current_track(Track),
    lap_cost(Track, Weather, Tyre, Age, WarmFlag, FW, RW, RH, Cost).

lap_cost_player(min, Weather, Tyre, Age, WarmFlag, FW, RW, RH, Cost) :-
    current_track(Track),
    base_lap_time(Track, Base),
    PaceAdj is 0.0,
    DegMult is 1.0,
    RiskMult is 1.0,

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

    ( WarmFlag =:= 1 -> warmup_penalty(Tyre, WUP) ; WUP = 0.0 ),

    ride_height_pace_adjust(RH, RHAdj),

    Cost is Base + PaceAdj + DragPen + WetAdj + DegPen + WrongPen + RiskPen + WUP + RHAdj.

% Convenience: update only weather from Python sampling
% set_weather(+State, +NewWeather, -NewState)
set_weather(state(L, _W, My, Opp), NewW, state(L, NewW, My, Opp)).

% init_state(+LapsLeft, +Weather, +MyTyre, +OppTyre, -State)
% Used lists start with starting tyre; plank wear starts at 0.
% Times start at 0.
init_state(LapsLeft, Weather, MyTyre, OppTyre,
           state(LapsLeft, Weather,
                 my(MyTyre, 0, [MyTyre], 0.0, 0, 0.0),
                 opp(OppTyre, 0, [OppTyre], 0.0, 0, 0.0))).