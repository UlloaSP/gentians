% Invented definitions use earlier invention layers or background predicates.
% Calling ordinary learnable predicates could introduce indirect cycles.
% Headless clauses cannot consume invented predicates under this language policy.
% Every body occurrence counts: ordinary literals, conditions, and the atoms and
% conditions of every aggregate form.
%   ha(X) :- d(X), hb(X).                 pruned when hb is not an earlier layer
%   ha(X) :- d(X), 1<={hb(Y):d(Y)}.       pruned for the same reason
%   :- 1<={hb(X):d(X)}.                   pruned: a constraint uses hb


% DEFINITION, local helper. body_dependency(Pred): the candidate clause reads
% predicate Pred.
%   Pred  signed predicate id that occurs anywhere the clause depends on it,
%         under either polarity.
% Collects every way a clause can read a predicate so the three constraints
% below test one relation. Used only in this file.
% Case 1: a plain body atom, positive or default negated.
body_dependency(Pred) :- normal_literal(body, _, _, Pred, _).

% DEFINITION, local helper. Same predicate. Case 2: a conditional construct:
% the conclusion of a body conditional, or a condition attached in head or
% body (representation/conditionals.lp).
body_dependency(Pred) :- conditional_dependency(_, _, Pred).

% DEFINITION, local helper. Same predicate. Case 3: a condition atom of a
% body aggregate of the single-element equality subset.
body_dependency(Pred) :-
    selected(body, _, Mode),
    aggregate_condition_atom(Mode, _, Pred, _).

% DEFINITION, local helper. Same predicate. Case 4: the conclusion atom of an
% element of a body set aggregate, as hb in "1 <= {hb(Y) : d(Y)}".
body_dependency(Pred) :-
    selected(body, _, Mode),
    aggregate_element_atom(Mode, _, Pred, _).

% DEFINITION, local helper. Same predicate. Case 5: a condition atom of any
% element of any body aggregate.
body_dependency(Pred) :-
    selected(body, _, Mode),
    aggregate_element_condition_atom(Mode, _, _, Pred, _).

% A default-negated head `not e` depends on e and does not define it.
% DEFINITION, local helper. learnable_head_pred(Pred): the language bias lets
% some clause define Pred.
%   Pred  signed predicate id of a head template that is not default negated.
% It is a property of the task, not of the current model: it holds whether or
% not that head is selected. Used only by the second constraint below.
learnable_head_pred(Pred) :-
    mode_section(Mode, head),
    mode_atom(Mode, Pred, _),
    not negative_mode(Mode).

% CONSTRAINT. A clause defining an invented predicate may read invented
% predicates of strictly earlier layers only.
%   HeadPred, HeadLayer  invented predicate in the head and its layer.
%   BodyPred, BodyLayer  invented predicate the clause reads and its layer.
% With inv1 declared at layer 0 and inv2 at layer 1:
%   pruned: inv1(V0) :- d(V0), inv2(V0).     a later layer
%   pruned: inv2(V0) :- e(V0,V1), inv2(V1).  its own layer: no recursion
%   kept:   inv2(V0) :- d(V0), inv1(V0).     an earlier layer
:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, HeadLayer),
    body_dependency(BodyPred),
    invented_pred(BodyPred, BodyLayer),
    BodyLayer >= HeadLayer.

% CONSTRAINT. A clause defining an invented predicate may not read an
% ordinary learnable predicate (one with a head mode that is not invented).
%   HeadPred  invented predicate in the head.
%   BodyPred  predicate the clause reads.
% With target learnable, inv1 invented and d background:
%   pruned: inv1(V0) :- target(V0).       target could itself depend on inv1
%   kept:   inv1(V0) :- d(V0).
%   kept:   target(V0) :- inv1(V0).       the head is not invented
:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, _),
    body_dependency(BodyPred),
    learnable_head_pred(BodyPred),
    not invented_pred(BodyPred, _).

% CONSTRAINT. A headless clause may not read an invented predicate.
%   Pred  invented predicate the clause reads.
%   pruned: :- d(V0), inv1(V0).
%   kept:   :- d(V0), target(V0).
%   kept:   target(V0) :- inv1(V0).       it has a head
:- not selected_slot(head, _),
    body_dependency(Pred),
    invented_pred(Pred, _).
