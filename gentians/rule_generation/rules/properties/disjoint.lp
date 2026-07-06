% Closed-world disjoint argument property.
%
% Python emits disjoint_arg/4 for argument pairs that never share values in the
% observed closed world, and domain_disjoint_arg/4 when declared argument types
% have disjoint observed domains. This file rejects joins over such positions.
%
% Shared atom shapes used here:
% - disjoint_arg(Pred0,Arg0,Pred1,Arg1): explicit closed-world disjointness.
% - domain_disjoint_arg(Pred0,Arg0,Pred1,Arg1): type-domain disjointness.
% - join_disjoint_arg(Pred0,Arg0,Pred1,Arg1): local union alias.
% - positive_body_literal(Slot,Mode,Pred,Arity): selected positive body atom.
% - var_at(body,Slot,Arg,Var): variable at predicate argument Arg.

#defined disjoint_arg/4.
#defined domain_disjoint_arg/4.

% Rule: explicit disjointness participates in join pruning.
% Pred0/Arg0 and Pred1/Arg1 identify the two predicate argument positions.
join_disjoint_arg(Pred0,Arg0,Pred1,Arg1):- disjoint_arg(Pred0,Arg0,Pred1,Arg1).

% Rule: type-domain disjointness participates in join pruning.
% Same argument meanings as disjoint_arg/4, but derived from type domains.
join_disjoint_arg(Pred0,Arg0,Pred1,Arg1):- domain_disjoint_arg(Pred0,Arg0,Pred1,Arg1).

% Constraint: reject positive-body joins on disjoint argument positions.
% Slot0 and Slot1 are ordered positive literals. Pred0/Arg0 and Pred1/Arg1 are
% known disjoint positions. Reusing Var across them would make the body empty.
:- positive_body_literal(Slot0,_,Pred0,_),
    positive_body_literal(Slot1,_,Pred1,_),
    Slot0 < Slot1,
    join_disjoint_arg(Pred0,Arg0,Pred1,Arg1),
    var_at(body,Slot0,Arg0,Var),
    var_at(body,Slot1,Arg1,Var).
