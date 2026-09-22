% Order operands only for modes whose types, directions and labels allow
% interchange. Specialized flags are emitted by the mode compiler.

#defined add_mode/1.
#defined mul_mode/1.
#defined div_mode/1.
#defined mod_mode/1.
#defined abs_mode/1.

:- selected(body, Slot, Mode),
    add_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right),
    Left > Right.

:- selected(body, Slot, Mode),
    mul_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right),
    Left > Right.

:- selected(body, Slot, Mode),
    abs_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right),
    Left > Right.
