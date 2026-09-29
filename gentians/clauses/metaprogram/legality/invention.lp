% Invented definitions use earlier invention layers or background predicates.
% Calling ordinary learnable predicates could introduce indirect cycles.
% Headless clauses cannot consume invented predicates under this language policy.
% Every body occurrence counts: ordinary literals, conditions, and the atoms and
% conditions of every aggregate form.
%   ha(X) :- d(X), hb(X).                 pruned when hb is not an earlier layer
%   ha(X) :- d(X), 1<={hb(Y):d(Y)}.       pruned for the same reason
%   :- 1<={hb(X):d(X)}.                   pruned: a constraint uses hb


body_dependency(Pred) :- normal_literal(body, _, _, Pred, _).

body_dependency(Pred) :- conditional_dependency(_, _, Pred).

body_dependency(Pred) :-
    selected(body, _, Mode),
    aggregate_condition_atom(Mode, _, Pred, _).

body_dependency(Pred) :-
    selected(body, _, Mode),
    aggregate_element_atom(Mode, _, Pred, _).

body_dependency(Pred) :-
    selected(body, _, Mode),
    aggregate_element_condition_atom(Mode, _, _, Pred, _).

% A default-negated head `not e` depends on e and does not define it.
learnable_head_pred(Pred) :-
    mode_section(Mode, head),
    mode_atom(Mode, Pred, _),
    not negative_mode(Mode).

:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, HeadLayer),
    body_dependency(BodyPred),
    invented_pred(BodyPred, BodyLayer),
    BodyLayer >= HeadLayer.

:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, _),
    body_dependency(BodyPred),
    learnable_head_pred(BodyPred),
    not invented_pred(BodyPred, _).

:- not selected_slot(head, _),
    body_dependency(Pred),
    invented_pred(Pred, _).
