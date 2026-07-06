% Closed-world irreflexive-like predicate property.
%
% Asymmetric predicates, strict orders, and acyclic binary predicates cannot
% contain self-pairs. This file also rejects reversed positive pairs for these
% predicates.
%
% Shared atom shapes used here:
% - asymmetric_pred(Pred): explicit asymmetric predicate id.
% - strict_order_pred(Pred): strict order predicate id.
% - acyclic_pred(Pred): acyclic predicate id.
% - irreflexive_pred(Pred): local union alias.
% - positive_body_literal(Slot,Mode,Pred,2): selected positive binary body atom.
% - reversed_binary_vars(body,Slot0,body,Slot1): variables reversed between
%   two binary literals.
% - var_at(body,Slot,Arg,Var): binary argument assignment.

#defined asymmetric_pred/1.
#defined strict_order_pred/1.
#defined acyclic_pred/1.

% Rule: asymmetric predicates are irreflexive.
% Pred is predicate id.
irreflexive_pred(Pred):- asymmetric_pred(Pred).

% Rule: strict order predicates are irreflexive.
% Pred is predicate id.
irreflexive_pred(Pred):- strict_order_pred(Pred).

% Rule: acyclic predicates are irreflexive.
% Pred is predicate id.
irreflexive_pred(Pred):- acyclic_pred(Pred).

% Constraint: reject reversed positive pair for irreflexive-like predicates.
% Slot0 and Slot1 are ordered positive binary literals over same Pred. Reversed
% variables create a two-edge cycle.
:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    Slot0 < Slot1,
    irreflexive_pred(Pred),
    reversed_binary_vars(body,Slot0,body,Slot1).

% Constraint: reject self-pair for irreflexive-like predicates.
% Slot is positive binary literal Pred(Var,Var). Such self-loops contradict
% asymmetric/strict-order/acyclic evidence.
:- positive_body_literal(Slot,_,Pred,2),
    irreflexive_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).
