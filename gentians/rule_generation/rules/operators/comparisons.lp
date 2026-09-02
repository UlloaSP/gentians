% Comparison operator pruning and derived relations.
%
% This file handles generated comparison literals: self-comparison rejection,
% symmetric comparison canonicalization, normalized less-than / less-equal
% helper relations, direct contradiction pruning, transitive redundancy pruning,
% and known-distinct variable derivation.
%
% Shared atom shapes used here:
% - comparison_mode(Mode): derived atom. Mode renders as a comparison operator.
% - neq_comparison_mode(Mode): Python fact for != comparisons.
% - less_than_comparison_mode(Mode): Python fact for <.
% - greater_than_comparison_mode(Mode): Python fact for >.
% - leq_comparison_mode(Mode): Python fact for <=.
% - geq_comparison_mode(Mode): Python fact for >=.
% - strict_comparison_available: derived atom when < or > exists in mode space.
% - selected(body,Slot,Mode): selected body comparison literal.
% - var_at(body,Slot,Arg,Var): comparison argument assignment; Arg 0 is left
%   operand and Arg 1 is right operand.

% Python fact contract:
% - neq_comparison_mode(Mode): emitted by Python for != modes.
% - less_than_comparison_mode(Mode): emitted by Python for < modes.
% - greater_than_comparison_mode(Mode): emitted by Python for > modes.
% - leq_comparison_mode(Mode): emitted by Python for <= modes.
% - geq_comparison_mode(Mode): emitted by Python for >= modes.
% Python fact detail: neq_comparison_mode(Mode) marks != comparison modes.
#defined neq_comparison_mode/1.
#defined eq_comparison_mode/1.
% Python fact detail: less_than_comparison_mode(Mode) marks < comparison modes.
#defined less_than_comparison_mode/1.
% Python fact detail: greater_than_comparison_mode(Mode) marks > comparison modes.
#defined greater_than_comparison_mode/1.
% Python fact detail: leq_comparison_mode(Mode) marks <= comparison modes.
#defined leq_comparison_mode/1.
% Python fact detail: geq_comparison_mode(Mode) marks >= comparison modes.
#defined geq_comparison_mode/1.
#defined generic_comparison_mode/1.

comparison_mode(Mode):- generic_comparison_mode(Mode).

simple_comparison_mode(Mode):- neq_comparison_mode(Mode).
simple_comparison_mode(Mode):- eq_comparison_mode(Mode).
simple_comparison_mode(Mode):- less_than_comparison_mode(Mode).
simple_comparison_mode(Mode):- greater_than_comparison_mode(Mode).
simple_comparison_mode(Mode):- leq_comparison_mode(Mode).
simple_comparison_mode(Mode):- geq_comparison_mode(Mode).

% Rule: != modes are comparison modes.
% Mode is the Python id for a body operator rendered as !=.
comparison_mode(Mode):- neq_comparison_mode(Mode).

% Rule: < modes are comparison modes.
% Mode is the Python id for a body operator rendered as <.
comparison_mode(Mode):- less_than_comparison_mode(Mode).

% Rule: > modes are comparison modes.
% Mode is the Python id for a body operator rendered as >.
comparison_mode(Mode):- greater_than_comparison_mode(Mode).

% Rule: <= modes are comparison modes.
% Mode is the Python id for a body operator rendered as <=.
comparison_mode(Mode):- leq_comparison_mode(Mode).

% Rule: >= modes are comparison modes.
% Mode is the Python id for a body operator rendered as >=.
comparison_mode(Mode):- geq_comparison_mode(Mode).

% Rule: strict comparison modes are available when < exists.
% Mode is a comparison mode rendered as <. The derived atom lets the leq+neq
% pruning rule prefer a direct strict comparison without Python emitting a flag.
strict_comparison_available:- less_than_comparison_mode(_).

% Rule: strict comparison modes are available when > exists.
% Mode is a comparison mode rendered as >. > is normalized to lt_vars/2 below,
% so it is also enough to replace <= plus !=.
strict_comparison_available:- greater_than_comparison_mode(_).

% Constraint: reject comparing a variable with itself.
% Slot is comparison body slot. Mode is comparison mode. Var appears in both
% argument 0 and argument 1, making comparisons such as V0 < V0 or V0 != V0
% impossible, and V0 == V0 redundant.
:- selected(body,Slot,Mode),
    simple_comparison_mode(Mode),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).

% Constraint: canonicalize != comparisons.
% Mode renders as !=. Left and Right are argument variables. Since Left != Right
% has same meaning as Right != Left, descending variable order is rejected.
:- selected(body,Slot,Mode),
    neq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

% Rule: normalize a selected < comparison into lt_vars(Left,Right).
% Left is argument 0, Right is argument 1. lt_vars always means Left < Right
% regardless of rendered operator direction.
lt_vars(Left,Right):-
    selected(body,Slot,Mode),
    less_than_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

% Rule: normalize a selected > comparison into lt_vars(Right,Left).
% Rendered Left > Right means Right < Left. This keeps all strict-order pruning
% in terms of lt_vars/2.
lt_vars(Right,Left):-
    selected(body,Slot,Mode),
    greater_than_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

% Rule: normalize a selected <= comparison into leq_vars(Left,Right).
% Left is argument 0, Right is argument 1. leq_vars always means Left <= Right.
leq_vars(Left,Right):-
    selected(body,Slot,Mode),
    leq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

% Rule: normalize a selected >= comparison into leq_vars(Right,Left).
% Rendered Left >= Right means Right <= Left. This keeps all non-strict-order
% pruning in terms of leq_vars/2.
leq_vars(Right,Left):-
    selected(body,Slot,Mode),
    geq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

% Constraint: reject contradictory strict comparisons.
% Left < Right and Right < Left cannot both hold.
:- lt_vars(Left,Right), lt_vars(Right,Left).

% Constraint: reject strict comparison contradicted by reverse non-strict one.
% Left < Right and Right <= Left cannot both hold.
:- lt_vars(Left,Right), leq_vars(Right,Left).

% Constraint: reject redundant non-strict copy of strict comparison.
% Left < Right already implies Left <= Right. Keeping both is redundant.
:- lt_vars(Left,Right), leq_vars(Left,Right).

% Constraint: reject two-way non-strict comparisons.
% Left <= Right and Right <= Left imply equality, which should be represented by
% equality if needed, not by two ordering literals.
:- leq_vars(Left,Right), leq_vars(Right,Left).

% Constraint: reject != when strict comparison already proves distinctness.
% Left < Right implies Left != Right.
:- lt_vars(Left,Right), neq_vars(Left,Right).

% Constraint: reject <= plus != when strict comparisons are available.
% If strict operators exist, Left <= Right and Left != Right can be represented
% more directly as Left < Right.
:- strict_comparison_available, leq_vars(Left,Right), neq_vars(Left,Right).

% Constraint: reject transitive strict shortcut.
% Left < Middle and Middle < Right already imply Left < Right, so the explicit
% Left < Right literal is redundant.
:- lt_vars(Left,Right), lt_vars(Left,Middle), lt_vars(Middle,Right).

% Constraint: reject strict shortcut via strict then non-strict chain.
% Left < Middle and Middle <= Right already imply Left < Right.
:- lt_vars(Left,Right), lt_vars(Left,Middle), leq_vars(Middle,Right).

% Constraint: reject strict shortcut via non-strict then strict chain.
% Left <= Middle and Middle < Right already imply Left < Right.
:- lt_vars(Left,Right), leq_vars(Left,Middle), lt_vars(Middle,Right).

% Constraint: reject non-strict shortcut implied by strict-strict chain.
% Left < Middle and Middle < Right imply Left <= Right, making explicit
% Left <= Right redundant.
:- leq_vars(Left,Right), lt_vars(Left,Middle), lt_vars(Middle,Right).

% Constraint: reject non-strict shortcut implied by strict then non-strict chain.
% Left < Middle and Middle <= Right imply Left <= Right.
:- leq_vars(Left,Right), lt_vars(Left,Middle), leq_vars(Middle,Right).

% Constraint: reject non-strict shortcut implied by non-strict then strict chain.
% Left <= Middle and Middle < Right imply Left <= Right.
:- leq_vars(Left,Right), leq_vars(Left,Middle), lt_vars(Middle,Right).

% Constraint: reject non-strict shortcut implied by non-strict chain.
% Left <= Middle and Middle <= Right imply Left <= Right.
:- leq_vars(Left,Right), leq_vars(Left,Middle), leq_vars(Middle,Right).

% Constraint: reject != implied by strict-strict chain.
% Left < Middle and Middle < Right imply Left != Right.
:- neq_vars(Left,Right), lt_vars(Left,Middle), lt_vars(Middle,Right).

% Constraint: reject != implied by strict then non-strict chain.
% Left < Middle and Middle <= Right imply Left != Right.
:- neq_vars(Left,Right), lt_vars(Left,Middle), leq_vars(Middle,Right).

% Constraint: reject != implied by non-strict then strict chain.
% Left <= Middle and Middle < Right imply Left != Right.
:- neq_vars(Left,Right), leq_vars(Left,Middle), lt_vars(Middle,Right).

% Rule: derive explicit inequality relation from selected != literal.
% Left is argument 0, Right is argument 1.
neq_vars(Left,Right):-
    selected(body,Slot,Mode),
    neq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

% Rule: inequality is symmetric.
% If Left != Right, Right != Left is also true for downstream pruning.
neq_vars(Right,Left):- neq_vars(Left,Right).

% Rule: explicit != proves two variables are known distinct.
% Left and Right are variables in neq_vars/2.
known_distinct_vars(Left,Right):- neq_vars(Left,Right).

% Rule: any strict comparison proves two variables are known distinct.
% lt_vars already normalizes both rendered < and rendered > comparisons, so no
% second strict-comparison helper is needed.
known_distinct_vars(Left,Right):- lt_vars(Left,Right).

% Rule: known distinctness is symmetric.
% Downstream modules may query either direction.
known_distinct_vars(Right,Left):- known_distinct_vars(Left,Right).
