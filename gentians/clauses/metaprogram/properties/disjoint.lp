% Closed-world disjoint argument property.
%
% Python emits disjoint_arg/4 for argument pairs that never share values in the
% observed closed world. This file rejects joins over such positions.

#defined disjoint_arg/4.
#defined tuple_mutex_pred/3.
#defined tuple_mutex_arg/3.

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

:- positive_body_literal(Slot0,_,Pred0,Arity),
    positive_body_literal(Slot1,_,Pred1,Arity),
    Slot0 != Slot1,
    tuple_mutex_pred(Pred0,Pred1,Projection),
    not tuple_mutex_vars_differ(Slot0,Slot1,Projection).
