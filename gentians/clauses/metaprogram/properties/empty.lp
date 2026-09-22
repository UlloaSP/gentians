% Closed-world empty predicate property.
%
% Python emits empty_pred(Pred) when predicate Pred has no true ground facts in
% the closed-world evidence. Positive uses are impossible; negative uses are
% redundant because not Pred(...) is always true.

#defined empty_pred/1.

:- positive_body_literal(Slot,_,Pred,_),
    empty_pred(Pred).

:- negative_body_literal(Slot,_,Pred,_),
    empty_pred(Pred).
