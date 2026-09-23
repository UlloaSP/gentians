% Assign one variable to each flattened placeholder of a selected mode.
% Rendered predicate arity and placeholder count can differ for nested terms.
% Fixed terms live in mode_shape/2 and require no variable assignment.


arg(Section, Slot, Arg) :-
    selected(Section, Slot, Mode),
    mode_variable_arg(Mode, Arg).

1 { var_at(Section, Slot, Arg, Var) : var(Var) } 1 :- arg(Section, Slot, Arg).

pooled_body_alternative_var(Slot, Alternative, Var) :-
    selected(body, Slot, Mode),
    mode_pool_alternative_arg(Mode, Alternative, Arg),
    var_at(body, Slot, Arg, Var).

pooled_body_missing_var(Slot, Var) :-
    selected(body, Slot, Mode),
    mode_pool_alternative(Mode, Alternative),
    var_at(body, Slot, _, Var),
    not pooled_body_alternative_var(Slot, Alternative, Var).

arg_type(Section, Slot, Arg, Type) :-
    selected(Section, Slot, Mode),
    mode_arg_type(Mode, Arg, Type).
