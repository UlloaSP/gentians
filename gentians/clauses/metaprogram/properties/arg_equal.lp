% Closed-world argument equality property.
%
% Python emits arg_equal_pred(Pred,Arg0,Arg1) when every true tuple of predicate
% Pred has equal values at argument positions Arg0 and Arg1. This file enforces
% that fact inside generated normal literals and aggregate condition atoms.

#defined arg_equal_pred/3.
#defined aggregate_condition_atom/5.

:- selected(Section,Slot,Mode),
    normal_literal(Section,Slot,Mode,Pred,_),
    arg_equal_pred(Pred,Arg0,Arg1),
    var_at(Section,Slot,Arg0,Var0),
    var_at(Section,Slot,Arg1,Var1),
    Var0 != Var1.

:- selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,_,Pred,Offset,_),
    arg_equal_pred(Pred,LocalArg0,LocalArg1),
    aggregate_condition_arg(Slot,Pred,LocalArg0,Var0),
    aggregate_condition_arg(Slot,Pred,LocalArg1,Var1),
    Var0 != Var1.
