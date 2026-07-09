% Closed-world disjoint argument property.
%
% Python emits disjoint_arg/4 for argument pairs that never share values in the
% observed closed world. This file rejects joins over such positions.
%
% Shared atom shapes used here:
% - disjoint_arg(Pred0,Arg0,Pred1,Arg1): explicit closed-world disjointness.
% - tuple_mutex_pred(Pred0,Pred1,Projection): tuple-level disjointness under
%   Projection from Pred0 args to Pred1 args.
% - tuple_mutex_arg(Projection,TargetArg,SourceArg): Pred1 TargetArg maps to
%   Pred0 SourceArg.
% - positive_body_literal(Slot,Mode,Pred,Arity): selected positive body atom.
% - var_at(body,Slot,Arg,Var): variable at predicate argument Arg.

% Python fact contract:
% - disjoint_arg(Pred0,Arg0,Pred1,Arg1): emitted by Python when observed values
%   at Pred0 argument Arg0 and Pred1 argument Arg1 never overlap.
% Python fact detail: disjoint_arg(Pred0,Arg0,Pred1,Arg1) marks two predicate argument domains as non-overlapping.
#defined disjoint_arg/4.
% Python fact detail: tuple_mutex_pred(Pred0,Pred1,Projection) marks two closed predicates as tuple-disjoint under a full argument projection.
#defined tuple_mutex_pred/3.
% Python fact detail: tuple_mutex_arg(Projection,TargetArg,SourceArg) maps projected tuple arguments.
#defined tuple_mutex_arg/3.

% Constraint: reject positive-body joins on disjoint argument positions.
% Slot0 and Slot1 are ordered positive literals. Pred0/Arg0 and Pred1/Arg1 are
% known disjoint positions. Reusing Var across them would make the body empty.
:- positive_body_literal(Slot0,_,Pred0,_),
    positive_body_literal(Slot1,_,Pred1,_),
    Slot0 < Slot1,
    disjoint_arg(Pred0,Arg0,Pred1,Arg1),
    var_at(body,Slot0,Arg0,Var),
    var_at(body,Slot1,Arg1,Var).

tuple_mutex_vars_differ(Slot0,Slot1,Projection):-
    tuple_mutex_arg(Projection,TargetArg,SourceArg),
    var_at(body,Slot0,SourceArg,SourceVar),
    var_at(body,Slot1,TargetArg,TargetVar),
    SourceVar != TargetVar.

% Constraint: reject two positive body literals whose full projected tuples
% cannot co-exist in closed-world evidence.
:- positive_body_literal(Slot0,_,Pred0,Arity),
    positive_body_literal(Slot1,_,Pred1,Arity),
    Slot0 != Slot1,
    tuple_mutex_pred(Pred0,Pred1,Projection),
    not tuple_mutex_vars_differ(Slot0,Slot1,Projection).
