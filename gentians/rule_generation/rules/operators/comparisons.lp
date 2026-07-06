% Comparison operator pruning and derived relations.
%
% This file handles generated comparison literals: self-comparison rejection,
% symmetric comparison canonicalization, normalized less-than / less-equal
% helper relations, direct contradiction pruning, transitive redundancy pruning,
% and known-distinct variable derivation.
%
% Shared atom shapes used here:
% - comparison_mode(Mode): Python fact. Mode renders as a comparison operator.
% - symmetric_comparison_mode(Mode): Python fact for == and != comparisons.
% - neq_comparison_mode(Mode): Python fact for != comparisons.
% - strict_comparison_mode(Mode): Python fact for < and > comparisons.
% - less_than_comparison_mode(Mode): Python fact for <.
% - greater_than_comparison_mode(Mode): Python fact for >.
% - leq_comparison_mode(Mode): Python fact for <=.
% - geq_comparison_mode(Mode): Python fact for >=.
% - strict_comparison_available: Python fact when < or > exists in mode space.
% - selected(body,Slot,Mode): selected body comparison literal.
% - var_at(body,Slot,Arg,Var): comparison argument assignment; Arg 0 is left
%   operand and Arg 1 is right operand.

#defined comparison_mode/1.
#defined symmetric_comparison_mode/1.
#defined neq_comparison_mode/1.
#defined strict_comparison_mode/1.
#defined less_than_comparison_mode/1.
#defined greater_than_comparison_mode/1.
#defined leq_comparison_mode/1.
#defined geq_comparison_mode/1.
#defined strict_comparison_available/0.
#defined canonical_prune/0.

% Constraint: reject comparing a variable with itself.
% Slot is comparison body slot. Mode is comparison mode. Var appears in both
% argument 0 and argument 1, making comparisons such as V0 < V0 or V0 != V0
% impossible, and V0 == V0 redundant.
:- selected(body,Slot,Mode),
    comparison_mode(Mode),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).

% Constraint: canonicalize symmetric comparisons.
% Mode is symmetric, currently == or !=. Left and Right are argument variables.
% Since Left != Right has same meaning as Right != Left, descending variable
% order is rejected when canonical_prune is enabled.
:- canonical_prune,
    selected(body,Slot,Mode),
    symmetric_comparison_mode(Mode),
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

% Rule: derive variables related by a strict comparison.
% Left and Right are the rendered argument order for either < or >. This helper
% is used only to derive known distinctness, not ordering direction.
strict_comparison_vars(Left,Right):-
    selected(body,Slot,Mode),
    strict_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

% Rule: explicit != proves two variables are known distinct.
% Left and Right are variables in neq_vars/2.
known_distinct_vars(Left,Right):- neq_vars(Left,Right).

% Rule: any strict comparison proves two variables are known distinct.
% Left and Right are variables participating in < or >.
known_distinct_vars(Left,Right):- strict_comparison_vars(Left,Right).

% Rule: known distinctness is symmetric.
% Downstream modules may query either direction.
known_distinct_vars(Right,Left):- known_distinct_vars(Left,Right).
