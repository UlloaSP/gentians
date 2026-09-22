% Order operands only for modes whose types, directions and labels allow
% interchange. Specialized flags are emitted by the mode compiler.


:- selected(body, Slot, Mode),
    add_mode(Mode),
    arithmetic_operand(Slot, left, Left),
    arithmetic_operand(Slot, right, Right),
    Left > Right.

:- selected(body, Slot, Mode),
    mul_mode(Mode),
    arithmetic_operand(Slot, left, Left),
    arithmetic_operand(Slot, right, Right),
    Left > Right.

:- selected(body, Slot, Mode),
    abs_mode(Mode),
    arithmetic_operand(Slot, left, Left),
    arithmetic_operand(Slot, right, Right),
    Left > Right.
