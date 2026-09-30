% Views of recognized three-placeholder arithmetic templates. Specialized
% mode flags preserve the compiler eligibility checks; these are not a new
% operator alphabet. Variable arguments are ids, not numeric values.



% DEFINITION, reusable. arithmetic_operand(Slot, Side, Variable): an operand
% of the arithmetic literal at body Slot.
%   Slot      body slot holding a complete template "Left op Right = Result".
%   Side      left or right, as declared in the template.
%   Variable  variable id written at that operand.
% Translates the storage position into a role, so no consumer computes
% offsets. Shared by the operator views below, legality/asp_safety.lp,
% legality/flow/closure.lp, symmetry/arithmetic.lp and
% pruning/redundancy/arithmetic.lp.
arithmetic_operand(Slot, Side, Variable) :-
    selected(body, Slot, Mode), mode_arithmetic_operand(Mode, Side, Position),
    var_at(body, Slot, Position, Variable).

% DEFINITION, reusable. arithmetic_result(Slot, Variable): the result of the
% arithmetic literal at body Slot.
%   Slot      body slot holding a complete arithmetic template.
%   Variable  variable id written at the result placeholder.
% Shared by the operator views below, legality/asp_safety.lp,
% legality/flow/closure.lp and pruning/redundancy/arithmetic.lp.
arithmetic_result(Slot, Variable) :-
    selected(body, Slot, Mode), mode_arithmetic_result(Mode, Position),
    var_at(body, Slot, Position, Variable).

% DEFINITION, reusable. addition(Slot, Left, Right, Result): the body states
% Left + Right = Result.
%   Slot    body slot of the literal.
%   Left    variable id of the left operand.
%   Right   variable id of the right operand.
%   Result  variable id of the sum.
% Example: "V0+V1=V2" in slot 3 yields addition(3,0,1,2). Shared by
% inference/numeric.lp (sign and order consequences),
% pruning/contradictions/numeric.lp and pruning/redundancy/numeric.lp.
addition(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), add_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).

% DEFINITION, reusable. multiplication(Slot, Left, Right, Result): the body
% states Left * Right = Result.
%   Arguments as in addition/4, Result being the product.
% Shared by inference/numeric.lp and pruning/contradictions/numeric.lp.
multiplication(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), mul_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).

% DEFINITION, reusable. division(Slot, Left, Right, Result): the body states
% Left / Right = Result (integer division).
%   Slot    body slot of the literal.
%   Left    variable id of the dividend.
%   Right   variable id of the divisor.
%   Result  variable id of the quotient.
% Operand order matters. Consumed by pruning/contradictions/numeric.lp.
division(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), div_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).

% DEFINITION, reusable. modulo(Slot, Left, Right, Result): the body states
% Left \ Right = Result.
%   Slot    body slot of the literal.
%   Left    variable id of the dividend.
%   Right   variable id of the divisor.
%   Result  variable id of the remainder.
% Operand order matters. Consumed by pruning/contradictions/numeric.lp.
modulo(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), mod_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).
