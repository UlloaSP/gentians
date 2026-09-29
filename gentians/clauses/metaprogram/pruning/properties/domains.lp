% Domain-relative properties hold only on the finite domain Python checked.
%
% Python emits domain_cover(Domain, Position, Pred, Arg) when every value of
% closed predicate Pred at argument Arg lies inside position Position of Domain.
% A variable bound there by a positive body literal therefore ranges over
% checked values. A variable bound only elsewhere (arithmetic, an aggregate
% result, another predicate) may take values the property says nothing about.
%
%   le(1,1). le(2,2). le(1,2). n(1..3).   reflexive on field {1,2}
%   h(X) :- le(X,Y), not le(X,X).          pruned: X comes from le's field
%   h(X) :- n(X), not le(X,X).             kept: X = 3 lies outside the field

domain_member(complement(Pred0, Pred1), Pred0) :- complement_pred(Pred0, Pred1).
domain_member(complement(Pred0, Pred1), Pred1) :- complement_pred(Pred0, Pred1).
domain_member(partition(Part), Pred) :- partition_pred(Part, Pred).
domain_member(universal(Pred), Pred) :- universal_pred(Pred).

covered_var(Domain, Position, Var, Slot) :-
    domain_cover(Domain, Position, Pred, Arg),
    positive_body_literal(Slot, _, Pred, _),
    var_at(body, Slot, Arg, Var).

covered_var(Domain, Position, Var) :- covered_var(Domain, Position, Var, _).

domain_position_covered(Domain, Slot, Position) :-
    var_at(body, Slot, Position, Var),
    covered_var(Domain, Position, Var).

domain_position_covered_elsewhere(Domain, Slot, Position) :-
    var_at(body, Slot, Position, Var),
    covered_var(Domain, Position, Var, Cover),
    Cover != Slot.

% A constant or an uncovered variable at any position blocks the pruning.
domain_literal_uncovered(Domain, Slot) :-
    domain_member(Domain, Pred),
    normal_literal(body, Slot, _, Pred, Arity),
    Position = 0..Arity-1,
    not domain_position_covered(Domain, Slot, Position).

domain_literal_uncovered_elsewhere(Domain, Slot) :-
    domain_member(Domain, Pred),
    normal_literal(body, Slot, _, Pred, Arity),
    Position = 0..Arity-1,
    not domain_position_covered_elsewhere(Domain, Slot, Position).
