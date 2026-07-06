% Closed-world total order predicate property.
%
% Python emits total_order_pred(Pred) when binary predicate Pred behaves like a
% total order over its observed domain. This file prunes redundant positive
% self-pairs, impossible negative self-pairs, and impossible pairs denying both
% directions between distinct variables.
%
% Shared atom shapes used here:
% - total_order_pred(Pred): property fact for binary predicate id.
% - positive_body_literal/4 and negative_body_literal/4: selected body atoms.
% - var_at(body,Slot,Arg,Var): binary argument variables.
% - positive_body_var_outside_slot(Slot,Var): Var is grounded elsewhere.

#defined total_order_pred/1.

% Constraint: reject redundant positive total-order self-pair.
% Slot is Pred(Var,Var). Total orders are reflexive, so if Var is already
% guarded outside Slot this literal adds no information.
:- positive_body_literal(Slot,_,Pred,2),
    total_order_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var),
    positive_body_var_outside_slot(Slot,Var).

% Constraint: reject negative total-order self-pair.
% not Pred(Var,Var) contradicts total-order reflexivity.
:- negative_body_literal(Slot,_,Pred,2),
    total_order_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).

% Constraint: reject negating both directions of a total order.
% Slot0 is not Pred(Left,Right); Slot1 is not Pred(Right,Left). Left != Right
% means distinct variables. In a total order at least one direction must hold.
:- negative_body_literal(Slot0,_,Pred,2),
    negative_body_literal(Slot1,_,Pred,2),
    Slot0 < Slot1,
    total_order_pred(Pred),
    var_at(body,Slot0,0,Left),
    var_at(body,Slot0,1,Right),
    Left != Right,
    var_at(body,Slot1,0,Right),
    var_at(body,Slot1,1,Left).
