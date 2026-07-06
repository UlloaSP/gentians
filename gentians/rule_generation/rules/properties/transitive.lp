% Closed-world transitive predicate property.
%
% This file owns transitive pruning: reject explicit transitive-closure
% redundancies and negative literals contradicting such closure. Stronger
% properties such as strict_order and total_order derive transitive_pred(Pred)
% in their own files.
%
% Shared atom shapes used here:
% - transitive_pred(Pred): property atom for binary predicate id Pred.
% - positive_body_literal/4 and negative_body_literal/4: selected body atoms.
% - var_at(body,Slot,0,X), var_at(body,Slot,1,Y): binary edge variables.

% Python fact contract:
% - transitive_pred(Pred): emitted by Python when binary predicate id Pred is
%   directly transitive in closed-world evidence. Other ASP property files may
%   also derive transitive_pred(Pred) when their stronger property implies it.
% Python fact detail: transitive_pred(Pred) marks binary predicate id Pred as transitive.
#defined transitive_pred/1.

% Constraint: reject explicit positive transitive closure literal.
% Slot0 is Pred(X,Y), Slot1 is Pred(Y,Z), Slot2 is Pred(X,Z). Slot order avoids
% checking all permutations. Slot2 is redundant because transitivity derives it.
:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    positive_body_literal(Slot2,_,Pred,2),
    Slot0 < Slot1,
    Slot1 < Slot2,
    transitive_pred(Pred),
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
    transitive_pred(Pred),
    var_at(body,Slot0,0,X),
    var_at(body,Slot0,1,Y),
    var_at(body,Slot1,0,Y),
    var_at(body,Slot1,1,Z),
    var_at(body,Slot2,0,X),
    var_at(body,Slot2,1,Z).
