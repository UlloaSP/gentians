% Closed-world argument equality property.
%
% Python emits arg_equal_pred(Pred,Arg0,Arg1) when every true tuple of predicate
% Pred has equal values at argument positions Arg0 and Arg1. This file enforces
% that fact inside generated normal literals and aggregate condition atoms.
%
% Shared atom shapes used here:
% - arg_equal_pred(Pred,Arg0,Arg1): property fact. Pred is predicate id; Arg0
%   and Arg1 are zero-based argument indexes that must use same variable.
% - normal_literal(Section,Slot,Mode,Pred,Arity): selected normal literal.
% - aggregate_condition_atom(Mode,AtomIndex,Pred,Offset,Arity): aggregate
%   condition predicate metadata.
% - aggregate_condition_arg(Slot,Pred,LocalArg,Var): variable at local condition
%   argument LocalArg for predicate Pred inside aggregate Slot.
% - var_at(Section,Slot,Arg,Var): variable at normal literal argument Arg.

% Python fact contract:
% - arg_equal_pred(Pred,Arg0,Arg1): emitted by Python when predicate id Pred
%   always has equal values at zero-based argument positions Arg0 and Arg1.
% - aggregate_condition_atom(Mode,AtomIndex,Pred,Offset,Arity): emitted by
%   Python for aggregate condition atoms so the same property can prune inside
%   aggregates.
% Python fact detail: arg_equal_pred(Pred,Arg0,Arg1) means arguments Arg0 and Arg1 of Pred must be equal.
#defined arg_equal_pred/3.
% Python fact detail: aggregate_condition_atom(Mode,AtomIndex,Pred,Offset,Arity) describes one aggregate condition atom; Offset is flattened arg offset.
#defined aggregate_condition_atom/5.

% Constraint: normal literal must respect known equal argument positions.
% Section/Slot/Mode identify a selected normal literal. Pred owns the property.
% Arg0 and Arg1 are positions known equal. Var0 and Var1 are generated variables
% placed there. Var0 != Var1 contradicts closed-world equality evidence.
:- selected(Section,Slot,Mode),
    normal_literal(Section,Slot,Mode,Pred,_),
    arg_equal_pred(Pred,Arg0,Arg1),
    var_at(Section,Slot,Arg0,Var0),
    var_at(Section,Slot,Arg1,Var1),
    Var0 != Var1.

% Constraint: aggregate condition atom must respect equal argument positions.
% Slot is aggregate body slot. Mode identifies aggregate mode. Pred is one
% condition predicate inside that aggregate. LocalArg0/LocalArg1 are indexes
% within that condition atom, not flattened aggregate indexes. Var0 and Var1
% must match.
:- selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,_,Pred,Offset,_),
    arg_equal_pred(Pred,LocalArg0,LocalArg1),
    aggregate_condition_arg(Slot,Pred,LocalArg0,Var0),
    aggregate_condition_arg(Slot,Pred,LocalArg1,Var1),
    Var0 != Var1.
