% Closed-world symmetric predicate property.
%
% Python emits symmetric_pred(Pred) when binary predicate Pred is symmetric:
% Pred(X, Y) and Pred(Y, X) have same truth value. This file keeps only one
% variable orientation for selected literals and aggregate condition atoms.


% CONSTRAINT. A plain atom of a symmetric predicate writes its two variables
% in ascending id order; the swapped atom means the same.
%   Section, Slot, Mode  the plain atom, in head or body and of either
%                        polarity.
%   Pred                 its predicate, symmetric and binary.
%   Left, Right          variable ids at arguments 0 and 1.
% With friend/2 symmetric:
%   pruned: h(V0,V1) :- p(V0), p(V1), friend(V1,V0).
%   kept:   h(V0,V1) :- p(V0), p(V1), friend(V0,V1).
%   pruned: h(V0,V1) :- p(V0), p(V1), not friend(V1,V0).
:- selected(Section, Slot, Mode),
    normal_literal(Section, Slot, Mode, Pred, 2),
    symmetric_pred(Pred),
    var_at(Section, Slot, 0, Left),
    var_at(Section, Slot, 1, Right),
    Left > Right.

% CONSTRAINT. The same orientation inside an aggregate: a condition atom of a
% symmetric predicate writes its two variables in ascending id order.
%   Slot             body slot of an aggregate of the single-element subset.
%   Condition, Pred  a condition occurrence and its predicate, symmetric and
%                    binary.
%   Left, Right      variable ids at arguments 0 and 1 of that condition.
% With friend/2 symmetric:
%   pruned: #count{V1 : friend(V1,V0)} = V2
%   kept:   #count{V1 : friend(V0,V1)} = V2
:- selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Pred, 2),
    symmetric_pred(Pred),
    aggregate_condition_arg(Slot, Condition, Pred, 0, Left),
    aggregate_condition_arg(Slot, Condition, Pred, 1, Right),
    Left > Right.
