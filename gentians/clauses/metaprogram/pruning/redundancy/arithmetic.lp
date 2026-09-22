% Reject repeated computations and the existing removable common-factor form.
% Equal modes are tuple-sorted, so identical inputs occupy adjacent slots.
% Different result ids are syntactic bindings, not a proof of unequal values.

#defined add_mode/1.
#defined mul_mode/1.
#defined div_mode/1.
#defined mod_mode/1.
#defined abs_mode/1.

arithmetic_input_differs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    arithmetic_mode(Mode),
    Slot1 = Slot0 + 1,
    Arg = 0..1,
    var_at(body, Slot0, Arg, Left),
    var_at(body, Slot1, Arg, Right),
    Left != Right.

same_arithmetic_inputs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    arithmetic_mode(Mode),
    Slot1 = Slot0 + 1,
    not arithmetic_input_differs(Slot0, Slot1).

:- same_arithmetic_inputs(Slot0, Slot1),
    var_at(body, Slot0, 2, Result0),
    var_at(body, Slot1, 2, Result1),
    Result0 != Result1.

:- selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    add_mode(Mode),
    Slot0 < Slot1,
    var_at(body, Slot0, 0, Left),
    var_at(body, Slot0, 1, Left),
    var_at(body, Slot0, 2, Result),
    var_at(body, Slot1, 0, Right),
    var_at(body, Slot1, 1, Right),
    var_at(body, Slot1, 2, Result),
    normal_positive_body_var(Left),
    normal_positive_body_var(Right),
    Left != Right.
