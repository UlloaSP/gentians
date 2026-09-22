% Positive addition already entails the selected operand/result comparison.
% Positivity comes from inference/numeric.lp and its task-domain assumptions.

:- addition(Slot, Left, Right, Result),
    positive_value(Right),
    selected_lt(Left, Result).

:- addition(Slot, Left, Right, Result),
    positive_value(Left),
    selected_lt(Right, Result).
