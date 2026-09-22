% Views of recognized three-placeholder arithmetic templates. Specialized
% mode flags preserve the compiler eligibility checks; these are not a new
% operator alphabet. Variable arguments are ids, not numeric values.



arithmetic_operand(Slot, Side, Variable) :-
    selected(body, Slot, Mode), mode_arithmetic_operand(Mode, Side, Position),
    var_at(body, Slot, Position, Variable).

arithmetic_result(Slot, Variable) :-
    selected(body, Slot, Mode), mode_arithmetic_result(Mode, Position),
    var_at(body, Slot, Position, Variable).

addition(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), add_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).

multiplication(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), mul_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).

division(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), div_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).

modulo(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), mod_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).
