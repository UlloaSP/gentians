% Track grounding safety independently from mode-directed readiness.
% Positive normal body atoms bind their variables. Arithmetic results become
% safe after their operands; aggregate results are safe outputs. Relation
% outputs proved safe by Clingo are handled in legality/flow/closure.lp.

asp_safe(Var) :- aggregate_result_var(_, Var).

normal_positive_body_var(Var) :-
    positive_body_literal(Slot, Mode, _, _),
    var_at(body, Slot, _, Var).

asp_safe(Var) :- normal_positive_body_var(Var).

head_var(Var) :-
    var_at(head, Slot, Arg, Var),
    not conditional_local_at(head, Slot, Arg).

negated_var(Var) :-
    negative_body_literal(Slot, Mode, _, _),
    var_at(body, Slot, _, Var).

comparison_var(Var) :-
    selected(body, Slot, Mode),
    comparison_mode(Mode),
    var_at(body, Slot, Arg, Var),
    not mode_arg_direction(Mode, Arg, output).

arithmetic_operand_var(Var) :-
    selected(body, Slot, Mode),
    arithmetic_mode(Mode),
    Arg = 0..1,
    var_at(body, Slot, Arg, Var).

arithmetic_result_safe(Slot) :-
    selected(body, Slot, Mode),
    arithmetic_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right),
    asp_safe(Left),
    asp_safe(Right).

asp_safe(Var) :-
    arithmetic_result_safe(Slot),
    var_at(body, Slot, 2, Var).

:- head_var(Var), not asp_safe(Var).

:- negated_var(Var), not asp_safe(Var).

:- comparison_var(Var), not asp_safe(Var).

:- arithmetic_operand_var(Var), not asp_safe(Var).
