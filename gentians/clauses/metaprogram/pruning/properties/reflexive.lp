% Reflexivity holds on the field Python checked (see domains.lp).
% A positive self-pair is redundant when another positive literal binds its
% variable inside that field. A negative self-pair is then impossible.
%   le reflexive on {1,2}:  h(X) :- le(X,Y), le(X,X).   pruned (redundant)
%                           h(X) :- n(X), not le(X,X).  kept when n reaches 3


:- positive_body_literal(Slot, _, Pred, 2),
    reflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var),
    covered_var(field(Pred), 0, Var, Cover),
    Cover != Slot.

:- negative_body_literal(Slot, _, Pred, 2),
    reflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var),
    covered_var(field(Pred), 0, Var).
