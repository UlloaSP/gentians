% Reflexivity holds on the field Python checked (see domains.lp).
% A positive self-pair is redundant when another positive literal binds its
% variable inside that field. A negative self-pair is then impossible.
%   le reflexive on {1,2}:  h(X) :- le(X,Y), le(X,X).   pruned (redundant)
%                           h(X) :- n(X), not le(X,X).  kept when n reaches 3


% CONSTRAINT. A positive self-pair of a reflexive predicate is redundant when
% a different positive body atom already binds its variable inside the field.
%   Slot   body slot of the positive atom Pred(Var,Var).
%   Pred   a reflexive binary predicate.
%   Var    the single variable id written at both arguments.
%   Cover  body slot of another positive atom that binds Var inside
%          field(Pred); it must differ from Slot, since the self-pair cannot
%          justify its own removal.
% With le/2 reflexive on its field:
%   pruned: h(V0) :- le(V0,V1), le(V0,V0).      V0 is in the field through le(V0,V1)
%   kept:   h(V0) :- le(V0,V0).                 the self-pair is what binds V0
%   kept:   h(V0) :- n(V0), le(V0,V0).          when n can reach values outside
%                                               the field, the atom filters them
:- positive_body_literal(Slot, _, Pred, 2),
    reflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var),
    covered_var(field(Pred), 0, Var, Cover),
    Cover != Slot.

% CONSTRAINT. A negated self-pair of a reflexive predicate is impossible when
% a positive body atom binds its variable inside the field.
%   Slot  body slot of the negated atom "not Pred(Var,Var)".
%   Pred  a reflexive binary predicate.
%   Var   the single variable id, bound inside field(Pred).
% With le/2 reflexive on its field:
%   pruned: h(V0) :- le(V0,V1), not le(V0,V0).
%   kept:   h(V0) :- n(V0), not le(V0,V0).      when n can reach values outside
%                                               the field
:- negative_body_literal(Slot, _, Pred, 2),
    reflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var),
    covered_var(field(Pred), 0, Var).
