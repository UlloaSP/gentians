% Closed-world single-input functional dependency property.
%
% Python emits functional_pred(Pred, Input, Output) when predicate Pred maps each
% value at argument Input to only one value at argument Output. Positive pairs
% with distinct output ids are excluded by the variable-identification policy:
% the dependency equates their values, not their syntactic ids. Negative-pair
% pruning instead requires a proof that the output values differ.

#defined functional_pred/3.

:- positive_body_literal(Slot0, _, Pred, _),
    positive_body_literal(Slot1, _, Pred, _),
    Slot0 < Slot1,
    functional_pred(Pred, Input, Output),
    var_at(body, Slot0, Input, Same),
    var_at(body, Slot1, Input, Same),
    var_at(body, Slot0, Output, Out0),
    var_at(body, Slot1, Output, Out1),
    Out0 != Out1.

% A negative tuple with a provably different output is already implied by the positive tuple.

:- positive_body_literal(PosSlot, _, Pred, _),
    negative_body_literal(NegSlot, _, Pred, _),
    functional_pred(Pred, Input, Output),
    var_at(body, PosSlot, Input, Same),
    var_at(body, NegSlot, Input, Same),
    var_at(body, PosSlot, Output, Out0),
    var_at(body, NegSlot, Output, Out1),
    known_unequal_values(Out0, Out1).
