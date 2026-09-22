% Reject repeated computations and the existing removable common-factor form.
% Equal modes are tuple-sorted, so identical inputs occupy adjacent slots.
% Different result ids are syntactic bindings, not a proof of unequal values.


arithmetic_input_differs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    arithmetic_mode(Mode),
    Slot1 = Slot0 + 1,
    arithmetic_operand(Slot0, Side, Left),
    arithmetic_operand(Slot1, Side, Right),
    Left != Right.

same_arithmetic_inputs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    arithmetic_mode(Mode),
    Slot1 = Slot0 + 1,
    not arithmetic_input_differs(Slot0, Slot1).

:- same_arithmetic_inputs(Slot0, Slot1),
    arithmetic_result(Slot0, Result0),
    arithmetic_result(Slot1, Result1),
    Result0 != Result1.

:- selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    add_mode(Mode),
    Slot0 < Slot1,
    arithmetic_operand(Slot0, left, Left),
    arithmetic_operand(Slot0, right, Left),
    arithmetic_result(Slot0, Result),
    arithmetic_operand(Slot1, left, Right),
    arithmetic_operand(Slot1, right, Right),
    arithmetic_result(Slot1, Result),
    normal_positive_body_var(Left),
    normal_positive_body_var(Right),
    Left != Right.
