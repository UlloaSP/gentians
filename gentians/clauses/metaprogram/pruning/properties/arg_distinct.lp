% Closed-world argument distinctness property.
%
% Python emits arg_distinct_pred(Pred, Arg0, Arg1) when every true tuple of
% predicate Pred has different values at positions Arg0 and Arg1. Other
% property files may derive arg_distinct_pred/3 when they imply it; for example
% irreflexive.lp derives arg_distinct_pred(Pred, 0, 1) for binary predicates.
% This file rejects generated literals that assign the same variable to those
% positions.


% DEFINITION, local helper. arg_distinct_self_pair_owned_by_irreflexive(Slot,
% Mode, Pred): the literal is a positive body atom of an irreflexive binary
% predicate, whose self-pair irreflexive.lp already rejects.
%   Slot  body slot of the atom.
%   Mode  its mode id.
%   Pred  its predicate, binary and irreflexive.
% Used only, negated, by the constraint below, so that one clause is not
% rejected by two constraints for the same reason.
arg_distinct_self_pair_owned_by_irreflexive(Slot, Mode, Pred) :-
    positive_body_literal(Slot, Mode, Pred, 2),
    irreflexive_pred(Pred).

% CONSTRAINT. A plain atom may not write one variable at two argument
% positions that always hold different values. Positive, the atom can never
% be true; negated, it is always true and adds nothing.
%   Section, Slot, Mode  the plain atom, of either polarity.
%   Pred                 its predicate.
%   Arg0, Arg1           two argument positions proved distinct.
%   Var                  the single variable id written at both.
% With arg_distinct_pred(parent,0,1) and arg_distinct_pred(move,0,2):
%   pruned: :- d(V0), not parent(V0,V0).      always true
%   pruned: :- move(V0,V1,V0).                never true
%   kept:   :- parent(V0,V1).
% A positive body self-pair of an irreflexive binary predicate is left to
% pruning/properties/irreflexive.lp.
:- selected(Section, Slot, Mode),
    normal_literal(Section, Slot, Mode, Pred, _),
    arg_distinct_pred(Pred, Arg0, Arg1),
    var_at(Section, Slot, Arg0, Var),
    var_at(Section, Slot, Arg1, Var),
    not arg_distinct_self_pair_owned_by_irreflexive(Slot, Mode, Pred).

% CONSTRAINT. The same check inside an aggregate: a condition atom may not
% write one variable at two positions that always differ, since the condition
% would never hold.
%   Slot                  body slot of an aggregate of the single-element
%                         subset.
%   Condition, Pred       a condition occurrence and its predicate.
%   LocalArg0, LocalArg1  two argument positions of Pred proved distinct.
%   Var                   the single variable id written at both.
% With arg_distinct_pred(parent,0,1):
%   pruned: #count{V0 : parent(V0,V0)} = V1
%   kept:   #count{V0 : parent(V0,V1)} = V2
:- selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Pred, _),
    arg_distinct_pred(Pred, LocalArg0, LocalArg1),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg0, Var),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg1, Var).
