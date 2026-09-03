% Closed-world acyclic predicate property.
%
% Python emits acyclic_pred(Pred) when binary predicate Pred has no directed
% cycles in observed facts. This file rejects explicit three-edge positive
% cycles and rejects negative back-edges that contradict an existing positive
% path of length two.
%
% Shared atom shapes used here:
% - acyclic_pred(Pred): property fact for binary predicate id.
% - irreflexive_pred(Pred): derived property atom consumed by irreflexive.lp.
% - antisymmetric_pred(Pred): derived property atom consumed by antisymmetric.lp.
% - positive_body_literal(Slot,Mode,Pred,2): selected positive binary body atom.
% - negative_body_literal(Slot,Mode,Pred,2): selected negative binary body atom.
% - var_at(body,Slot,0,X): source variable of binary atom.
% - var_at(body,Slot,1,Y): target variable of binary atom.

% Python fact contract:
% - acyclic_pred(Pred): emitted by Python when closed-world analysis finds
%   binary predicate id Pred has no directed cycles in observed facts.
% Python fact detail: acyclic_pred(Pred) marks binary predicate id Pred as acyclic in closed-world evidence.
#defined acyclic_pred/1.

% Rule: acyclic predicates are irreflexive.
% Pred is the predicate id. A self-pair Pred(Var,Var) is a one-edge cycle, so
% irreflexive.lp owns the actual self-pair constraint.
irreflexive_pred(Pred):- acyclic_pred(Pred).

% Rule: acyclic predicates are antisymmetric.
% Pred is the predicate id. A reversed pair Pred(X,Y), Pred(Y,X) for X != Y is
% a two-edge cycle, so antisymmetric.lp owns that constraint.
antisymmetric_pred(Pred):- acyclic_pred(Pred).

% Constraint: reject positive three-cycle X->Y->Z->X.
% Slot0, Slot1, Slot2 are ordered positive body literals over same Pred. The
% variables form Pred(X,Y), Pred(Y,Z), Pred(Z,X), impossible for acyclic Pred.
:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    positive_body_literal(Slot2,_,Pred,2),
    Slot0 < Slot1,
    Slot1 < Slot2,
    acyclic_pred(Pred),
    var_at(body,Slot0,0,X),
    var_at(body,Slot0,1,Y),
    var_at(body,Slot1,0,Y),
    var_at(body,Slot1,1,Z),
    var_at(body,Slot2,0,Z),
    var_at(body,Slot2,1,X).

% Constraint: reject negative back-edge over positive two-step path.
% Slot0 and Slot1 provide positive path X->Y->Z. Slot2 is not Pred(Z,X). In an
% acyclic relation the back edge Z->X is impossible, so negating it is redundant.
:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    negative_body_literal(Slot2,_,Pred,2),
    acyclic_pred(Pred),
    var_at(body,Slot0,0,X),
    var_at(body,Slot0,1,Y),
    var_at(body,Slot1,0,Y),
    var_at(body,Slot1,1,Z),
    var_at(body,Slot2,0,Z),
    var_at(body,Slot2,1,X).
