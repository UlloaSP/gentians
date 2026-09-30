% Closed-world argument equality property.
%
% Python emits arg_equal_pred(Pred, Arg0, Arg1) when every true tuple of predicate
% Pred has equal values at argument positions Arg0 and Arg1. The enumerator
% chooses identical variable ids at these positions of positive literals, which
% can only be true for equal values. A negated literal with distinct ids is not
% equivalent: not same(X,Y) holds for every X != Y.


% CONSTRAINT. A positive body atom must write the same variable id at two
% argument positions that always hold equal values. With two ids the atom
% would force them equal, which the enumerator expresses with one id.
%   Slot        body slot of the positive atom.
%   Pred        its predicate.
%   Arg0, Arg1  two argument positions proved equal.
%   Var0, Var1  the two different variable ids found there.
% With arg_equal_pred(same,0,1):
%   pruned: h(V0) :- same(V0,V1).
%   kept:   h(V0) :- same(V0,V0).
%   kept:   h(V0) :- d(V0), d(V1), not same(V0,V1).   negation is not covered
:- positive_body_literal(Slot, _, Pred, _),
    arg_equal_pred(Pred, Arg0, Arg1),
    var_at(body, Slot, Arg0, Var0),
    var_at(body, Slot, Arg1, Var1),
    Var0 != Var1.

% CONSTRAINT. The same check inside an aggregate: a condition atom must write
% one variable id at two argument positions that always hold equal values.
%   Slot                  body slot of an aggregate of the single-element
%                         subset.
%   Condition, Pred       a condition occurrence and its predicate.
%   LocalArg0, LocalArg1  two argument positions of Pred proved equal.
%   Var0, Var1            the two different variable ids found there.
% With arg_equal_pred(same,0,1):
%   pruned: #count{V0,V1 : same(V0,V1)} = V2
%   kept:   #count{V0 : same(V0,V0)} = V1     by this constraint; the policy in
%           pruning/policies/aggregates.lp then rejects the repeated V0
:- selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Pred, _),
    arg_equal_pred(Pred, LocalArg0, LocalArg1),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg0, Var0),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg1, Var1),
    Var0 != Var1.
