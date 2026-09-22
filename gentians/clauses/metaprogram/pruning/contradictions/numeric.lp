% Reject impossible arithmetic/order combinations under the supplied numeric
% domain evidence. Inferred strict-order cycles are impossible.
% These checks inherit the task-relative assumptions of inference/numeric.lp.

% This cycle check also covers opposite selected strict comparisons and
% strict reversals of the operand/result order inferred from positive addition.
:- inferred_lt(Var, Var).

:- numeric_domain_nonnegative,
    addition(Slot, Left, _, Result),
    numeric_argument_var(Left),
    numeric_argument_var(Result),
    selected_lt(Result, Left).

:- numeric_domain_nonnegative,
    addition(Slot, _, Right, Result),
    numeric_argument_var(Right),
    numeric_argument_var(Result),
    selected_lt(Result, Right).

:- addition(Slot, Left, Right, Result),
    positive_value(Right),
    selected_leq(Result, Left).

:- addition(Slot, Left, Right, Result),
    positive_value(Left),
    selected_leq(Result, Right).

:- numeric_domain_positive,
    modulo(Slot, _, Divisor, Result),
    numeric_argument_var(Divisor),
    numeric_argument_var(Result),
    selected_leq(Divisor, Result).

:- numeric_domain_positive,
    multiplication(Slot, Left, Right, Result),
    numeric_argument_var(Left),
    numeric_argument_var(Right),
    numeric_argument_var(Result),
    selected_lt(Result, Left).

:- numeric_domain_positive,
    multiplication(Slot, Left, Right, Result),
    numeric_argument_var(Left),
    numeric_argument_var(Right),
    numeric_argument_var(Result),
    selected_lt(Result, Right).

:- numeric_domain_positive,
    division(Slot, Left, Right, Result),
    numeric_argument_var(Left),
    numeric_argument_var(Right),
    numeric_argument_var(Result),
    selected_lt(Left, Result).
