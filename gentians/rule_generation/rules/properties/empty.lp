% Closed-world empty predicate property.
%
% Python emits empty_pred(Pred) when predicate Pred has no true ground facts in
% the closed-world evidence. Positive uses are impossible; negative uses are
% redundant because not Pred(...) is always true.
%
% Shared atom shapes used here:
% - empty_pred(Pred): property fact for predicate id Pred.
% - positive_body_literal(Slot,Mode,Pred,Arity): selected positive body atom.
% - negative_body_literal(Slot,Mode,Pred,Arity): selected negated body atom.

% Python fact contract:
% - empty_pred(Pred): emitted by Python when closed-world extension of predicate
%   id Pred has no true tuples.
% Python fact detail: empty_pred(Pred) marks predicate id Pred as having empty closed-world extension.
#defined empty_pred/1.

% Constraint: reject positive use of an empty predicate.
% Slot is positive body slot. Pred has empty extension, so the body would never
% be satisfied.
:- positive_body_literal(Slot,_,Pred,_),
    empty_pred(Pred).

% Constraint: reject negative use of an empty predicate.
% not Pred(...) is always true for an empty predicate and adds no information.
:- negative_body_literal(Slot,_,Pred,_),
    empty_pred(Pred).
