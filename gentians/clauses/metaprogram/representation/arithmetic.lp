% Views of recognized three-placeholder arithmetic templates. Specialized
% mode flags preserve the compiler eligibility checks; these are not a new
% operator alphabet. Variable arguments are ids, not numeric values.

#defined add_mode/1.
#defined mul_mode/1.
#defined div_mode/1.
#defined mod_mode/1.

addition(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), add_mode(Mode),
    var_at(body, Slot, 0, Left), var_at(body, Slot, 1, Right),
    var_at(body, Slot, 2, Result).

multiplication(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), mul_mode(Mode),
    var_at(body, Slot, 0, Left), var_at(body, Slot, 1, Right),
    var_at(body, Slot, 2, Result).

division(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), div_mode(Mode),
    var_at(body, Slot, 0, Left), var_at(body, Slot, 1, Right),
    var_at(body, Slot, 2, Result).

modulo(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), mod_mode(Mode),
    var_at(body, Slot, 0, Left), var_at(body, Slot, 1, Right),
    var_at(body, Slot, 2, Result).
