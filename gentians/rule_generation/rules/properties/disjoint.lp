% Closed-world disjoint argument property.
%
% Python emits disjoint_arg/4 for argument pairs that never share values in the
% observed closed world. This file rejects joins over such positions.
%
% Shared atom shapes used here:
% - disjoint_arg(Pred0,Arg0,Pred1,Arg1): explicit closed-world disjointness.
% - positive_body_literal(Slot,Mode,Pred,Arity): selected positive body atom.
% - var_at(body,Slot,Arg,Var): variable at predicate argument Arg.

% Python fact contract:
% - disjoint_arg(Pred0,Arg0,Pred1,Arg1): emitted by Python when observed values
%   at Pred0 argument Arg0 and Pred1 argument Arg1 never overlap.
% Python fact detail: disjoint_arg(Pred0,Arg0,Pred1,Arg1) marks two predicate argument domains as non-overlapping.
#defined disjoint_arg/4.

% Constraint: reject positive-body joins on disjoint argument positions.
% Slot0 and Slot1 are ordered positive literals. Pred0/Arg0 and Pred1/Arg1 are
% known disjoint positions. Reusing Var across them would make the body empty.
:- positive_body_literal(Slot0,_,Pred0,_),
    positive_body_literal(Slot1,_,Pred1,_),
    Slot0 < Slot1,
    disjoint_arg(Pred0,Arg0,Pred1,Arg1),
    var_at(body,Slot0,Arg0,Var),
    var_at(body,Slot1,Arg1,Var).
