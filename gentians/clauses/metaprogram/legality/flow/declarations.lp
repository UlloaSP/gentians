% Classify directed modes, count required inputs and expose conditional roles.
% Counts are positions, not distinct variables: repeated input names still fill
% every declared input position.


conditional_global_input_var(Var) :-
    selected(Section, Slot, Mode),
    conditional_global_var(Section, Slot, Var),
    mode_arg_direction(Mode, Arg, input),
    var_at(Section, Slot, Arg, Var).

conditional_global_output_var(Var) :-
    selected(Section, Slot, Mode),
    conditional_global_var(Section, Slot, Var),
    mode_arg_direction(Mode, Arg, output),
    var_at(Section, Slot, Arg, Var).

directed_mode(Mode) :- mode_arg_direction(Mode, _, input), not conditional_mode(Mode).

directed_mode(Mode) :- mode_arg_direction(Mode, _, output), not conditional_mode(Mode).

input_count(Mode, Count) :-
    directed_mode(Mode),
    Count = #count{Arg : mode_arg_direction(Mode, Arg, input)}.

relation_input_count(Mode, Count) :-
    relation_output_mode(Mode),
    Count = #count {
        Arg : mode_variable_arg(Mode, Arg),
              not mode_arg_direction(Mode, Arg, output)
    }.
