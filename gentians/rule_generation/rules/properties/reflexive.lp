% Closed-world reflexive predicate property.
%
% Python emits reflexive_pred(Pred) when binary predicate Pred contains all
% self-pairs in the observed domain. Positive self-pairs are redundant when Var
% is already guarded elsewhere; negative self-pairs are impossible.
%
% Shared atom shapes used here:
% - reflexive_pred(Pred): property fact for binary predicate id.
% - positive_body_literal(Slot,Mode,Pred,2): selected positive binary body atom.
% - negative_body_literal(Slot,Mode,Pred,2): selected negative binary body atom.
% - var_at(body,Slot,0,Var) and var_at(body,Slot,1,Var): self-pair variables.
% - positive_body_var_outside_slot(Slot,Var): Var is grounded by another
%   positive body literal.

#defined reflexive_pred/1.

% Constraint: reject redundant positive reflexive self-pair.
% Slot is Pred(Var,Var). If Var also occurs in another positive body literal,
% reflexivity makes this literal always true and redundant.
:- positive_body_literal(Slot,_,Pred,2),
    reflexive_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var),
    positive_body_var_outside_slot(Slot,Var).

% Constraint: reject negative reflexive self-pair.
% not Pred(Var,Var) contradicts reflexive_pred(Pred).
:- negative_body_literal(Slot,_,Pred,2),
    reflexive_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).
