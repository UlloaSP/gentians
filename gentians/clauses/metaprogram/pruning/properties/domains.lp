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
%
% This file has no constraint of its own. Domain is one of the terms field(P),
% universal(P), complement(P,Q) or partition(Group).

% DEFINITION, local helper. domain_member(Domain, Pred): Pred is one of the
% predicates whose property is relative to Domain.
%   Domain  complement(Pred0, Pred1), partition(Part) or universal(Pred).
%   Pred    signed predicate id of a member. field(P) domains have no member
%           facts: reflexive.lp and total_order.lp query covered_var directly.
% Used only by the two domain_literal_uncovered views at the end.
% Case 1: the first predicate of a complement pair.
domain_member(complement(Pred0, Pred1), Pred0) :- complement_pred(Pred0, Pred1).
% DEFINITION, local helper. Same predicate. Case 2: the second predicate of a
% complement pair.
domain_member(complement(Pred0, Pred1), Pred1) :- complement_pred(Pred0, Pred1).
% DEFINITION, local helper. Same predicate. Case 3: each predicate of a
% partition.
domain_member(partition(Part), Pred) :- partition_pred(Part, Pred).
% DEFINITION, local helper. Same predicate. Case 4: a universal predicate.
domain_member(universal(Pred), Pred) :- universal_pred(Pred).

% DEFINITION, reusable. covered_var(Domain, Position, Var, Slot): the positive
% body atom at Slot binds Var to values inside one position of Domain.
%   Domain    the domain term.
%   Position  position of the domain whose values contain those of the
%             binding argument.
%   Var       variable id written at that argument.
%   Slot      body slot of the positive atom that binds it.
% The Slot is kept for consumers that must exclude a literal covering itself:
% pruning/properties/reflexive.lp and domain_position_covered_elsewhere below.
covered_var(Domain, Position, Var, Slot) :-
    domain_cover(Domain, Position, Pred, Arg),
    positive_body_literal(Slot, _, Pred, _),
    var_at(body, Slot, Arg, Var).

% DEFINITION, reusable. covered_var(Domain, Position, Var): some positive body
% atom binds Var inside that position of Domain.
%   Arguments as in covered_var/4, without the Slot.
% Shared by domain_position_covered below and by
% pruning/properties/reflexive.lp and total_order.lp.
covered_var(Domain, Position, Var) :- covered_var(Domain, Position, Var, _).

% DEFINITION, local helper. domain_position_covered(Domain, Slot, Position):
% argument Position of the body literal at Slot holds a variable whose values
% lie inside the same position of Domain.
%   Domain    the domain term.
%   Slot      body slot of the literal under inspection.
%   Position  one of its argument positions; it is also the domain position
%             consulted.
% Used only, negated, by domain_literal_uncovered below.
domain_position_covered(Domain, Slot, Position) :-
    var_at(body, Slot, Position, Var),
    covered_var(Domain, Position, Var).

% DEFINITION, local helper. domain_position_covered_elsewhere(Domain, Slot,
% Position): the same, but the covering positive atom is a different literal.
%   Arguments as above; Cover (body variable) is the slot of the covering
%   atom and differs from Slot.
% Needed when the inspected literal is itself positive: it must not justify
% its own removal. Used only, negated, by domain_literal_uncovered_elsewhere.
domain_position_covered_elsewhere(Domain, Slot, Position) :-
    var_at(body, Slot, Position, Var),
    covered_var(Domain, Position, Var, Cover),
    Cover != Slot.

% A constant or an uncovered variable at any position blocks the pruning.
% DEFINITION, reusable. domain_literal_uncovered(Domain, Slot): the body
% literal at Slot may denote a tuple outside Domain.
%   Domain  a domain with member predicates.
%   Slot    body slot of a plain atom, of either polarity, of a member
%           predicate, with some argument position that is not covered.
% Consumed, negated, by pruning/properties/complement.lp, partition.lp and
% universal.lp: their prunings apply only when every argument is covered.
domain_literal_uncovered(Domain, Slot) :-
    domain_member(Domain, Pred),
    normal_literal(body, Slot, _, Pred, Arity),
    Position = 0..Arity-1,
    not domain_position_covered(Domain, Slot, Position).

% DEFINITION, reusable. domain_literal_uncovered_elsewhere(Domain, Slot): some
% argument of the body literal at Slot is not covered by another literal.
%   Arguments as in domain_literal_uncovered/2.
% Consumed, negated, by pruning/properties/universal.lp to decide whether a
% positive atom is redundant.
domain_literal_uncovered_elsewhere(Domain, Slot) :-
    domain_member(Domain, Pred),
    normal_literal(body, Slot, _, Pred, Arity),
    Position = 0..Arity-1,
    not domain_position_covered_elsewhere(Domain, Slot, Position).
