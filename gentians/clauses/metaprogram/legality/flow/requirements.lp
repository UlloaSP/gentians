% Reject unmet inputs and outputs after the positive fixed point.
% Default-negated and conditional literals never produce global variables.

:- conditional_global_input_var(Var), not flow_bound(Var).

:- conditional_global_output_var(Var), not flow_produced(Var).

:- selected(body, Slot, Mode), arithmetic_mode(Mode), not ready_arithmetic(Slot).

:- selected(body, Slot, Mode),
    comparison_mode(Mode),
    var_at(body, Slot, Arg, Var),
    not mode_arg_direction(Mode, Arg, output),
    not flow_bound(Var).

:- selected(body, Slot, Mode),
   relation_output_mode(Mode),
   not ready_relation(Slot).

:- selected(body, Slot, Mode), directed_mode(Mode), not ready_literal(Slot).

:- selected(head, Slot, Mode),
    not conditional_mode(Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(head, Slot, Arg, Var),
    not flow_produced(Var).
