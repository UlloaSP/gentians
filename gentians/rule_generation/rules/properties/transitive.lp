% Closed-world transitive-like predicate property.
%
% Python emits transitive_pred/1, strict_order_pred/1, and total_order_pred/1
% for binary predicates where X->Y and Y->Z imply X->Z. This file rejects
% explicit transitive-closure redundancies and negative literals contradicting
% such closure.
%
% Shared atom shapes used here:
% - transitive_pred(Pred): explicit transitive predicate id.
% - strict_order_pred(Pred): strict order predicate id, also transitive.
% - total_order_pred(Pred): total order predicate id, also transitive.
% - transitive_like_pred(Pred): local union alias.
% - positive_body_literal/4 and negative_body_literal/4: selected body atoms.
% - var_at(body,Slot,0,X), var_at(body,Slot,1,Y): binary edge variables.

#defined transitive_pred/1.
#defined strict_order_pred/1.
#defined total_order_pred/1.

% Rule: explicit transitive predicates are transitive-like.
% Pred is predicate id.
transitive_like_pred(Pred):- transitive_pred(Pred).

% Rule: strict orders are transitive-like.
% Pred is predicate id.
transitive_like_pred(Pred):- strict_order_pred(Pred).

% Rule: total orders are transitive-like.
% Pred is predicate id.
transitive_like_pred(Pred):- total_order_pred(Pred).

% Constraint: reject explicit positive transitive closure literal.
% Slot0 is Pred(X,Y), Slot1 is Pred(Y,Z), Slot2 is Pred(X,Z). Slot order avoids
% checking all permutations. Slot2 is redundant because transitivity derives it.
:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    positive_body_literal(Slot2,_,Pred,2),
    Slot0 < Slot1,
    Slot1 < Slot2,
    transitive_like_pred(Pred),
    var_at(body,Slot0,0,X),
    var_at(body,Slot0,1,Y),
    var_at(body,Slot1,0,Y),
    var_at(body,Slot1,1,Z),
    var_at(body,Slot2,0,X),
    var_at(body,Slot2,1,Z).

% Constraint: reject negative literal contradicted by transitive path.
% Slot0 is Pred(X,Y), Slot1 is Pred(Y,Z), Slot2 is not Pred(X,Z). Transitivity
% requires Pred(X,Z), so the negative literal is impossible.
:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    negative_body_literal(Slot2,_,Pred,2),
    transitive_like_pred(Pred),
    var_at(body,Slot0,0,X),
    var_at(body,Slot0,1,Y),
    var_at(body,Slot1,0,Y),
    var_at(body,Slot1,1,Z),
    var_at(body,Slot2,0,X),
    var_at(body,Slot2,1,Z).
