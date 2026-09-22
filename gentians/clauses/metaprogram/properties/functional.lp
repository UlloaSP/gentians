% Closed-world single-input functional dependency property.
%
% Python emits functional_pred(Pred,Input,Output) when predicate Pred maps each
% value at argument Input to only one value at argument Output. This file prunes
% conflicting positive pairs and negative literals made redundant by a positive
% literal with the same input and a different output.

#defined functional_pred/3.

:- positive_body_literal(Slot0,_,Pred,_),
    positive_body_literal(Slot1,_,Pred,_),
    Slot0 < Slot1,
    functional_pred(Pred,Input,Output),
    var_at(body,Slot0,Input,Same),
    var_at(body,Slot1,Input,Same),
    var_at(body,Slot0,Output,Out0),
    var_at(body,Slot1,Output,Out1),
    Out0 != Out1.

% A negative tuple with a provably different output is already implied by the positive tuple.

:- positive_body_literal(PosSlot,_,Pred,_),
    negative_body_literal(NegSlot,_,Pred,_),
    functional_pred(Pred,Input,Output),
    var_at(body,PosSlot,Input,Same),
    var_at(body,NegSlot,Input,Same),
    var_at(body,PosSlot,Output,Out0),
    var_at(body,NegSlot,Output,Out1),
    known_distinct_vars(Out0,Out1).
