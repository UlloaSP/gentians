% Closed-world symmetric predicate property.
%
% Python emits symmetric_pred(Pred) when binary predicate Pred is symmetric:
% Pred(X,Y) and Pred(Y,X) have same truth value. This file keeps only one
% variable orientation for selected literals and aggregate condition atoms.

#defined symmetric_pred/1.
#defined aggregate_condition_atom/5.

:- selected(Section,Slot,Mode),
    normal_literal(Section,Slot,Mode,Pred,2),
    symmetric_pred(Pred),
    var_at(Section,Slot,0,Left),
    var_at(Section,Slot,1,Right),
    Left > Right.

:- selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,_,Pred,Offset,2),
    symmetric_pred(Pred),
    aggregate_condition_arg(Slot,Pred,0,Left),
    aggregate_condition_arg(Slot,Pred,1,Right),
    Left > Right.
