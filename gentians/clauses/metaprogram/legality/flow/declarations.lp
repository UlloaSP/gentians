% Classify directed modes, count required inputs and expose conditional roles.
% Counts are positions, not distinct variables: repeated input names still fill
% every declared input position.


% DEFINITION, reusable. conditional_global_input_var(Var): a conditional
% literal reads the clause-global variable Var at a position declared input.
%   Var  variable id that is global to the clause (legality/scopes.lp) and
%        sits at an input placeholder of a selected conditional, in head or
%        body.
% Consumed by legality/flow/requirements.lp: such an input must be bound.
conditional_global_input_var(Var) :-
    selected(Section, Slot, Mode),
    conditional_global_var(Section, Slot, Var),
    mode_arg_direction(Mode, Arg, input),
    var_at(Section, Slot, Arg, Var).

% DEFINITION, reusable. conditional_global_output_var(Section, Var): a
% conditional literal declares the clause-global variable Var as output.
%   Section  head or body: where the conditional is selected. The requirement
%            differs per section, so it is kept.
%   Var      clause-global variable id at an output placeholder of it.
% Consumed by legality/flow/requirements.lp. A conditional never produces a
% global variable, so another literal must produce it.
conditional_global_output_var(Section, Var) :-
    selected(Section, Slot, Mode),
    conditional_global_var(Section, Slot, Var),
    mode_arg_direction(Mode, Arg, output),
    var_at(Section, Slot, Arg, Var).

% DEFINITION, reusable. directed_mode(Mode): Mode declares a data direction.
%   Mode  id of a non-conditional template with at least one input or output
%         placeholder. A mode whose placeholders are all "any" is undirected.
% Shared by input_count below, legality/flow/seeds.lp (an undirected atom binds
% unconditionally) and legality/flow/requirements.lp (a directed literal must
% become ready).
% Case 1: the mode has an input placeholder.
directed_mode(Mode) :- mode_arg_direction(Mode, _, input), not conditional_mode(Mode).

% DEFINITION, reusable. Same predicate. Case 2: the mode has an output
% placeholder.
directed_mode(Mode) :- mode_arg_direction(Mode, _, output), not conditional_mode(Mode).

% DEFINITION, reusable. input_count(Mode, Count): how many inputs a directed
% mode requires.
%   Mode   id of a directed mode.
%   Count  number of its placeholder positions declared input; 0 for a mode
%          with outputs only. Positions are counted, not distinct variables.
% Consumed by legality/flow/closure.lp, which makes a literal ready once that
% many input positions hold bound variables.
input_count(Mode, Count) :-
    directed_mode(Mode),
    Count = #count{Arg : mode_arg_direction(Mode, Arg, input)}.

% DEFINITION, reusable. relation_input_count(Mode, Count): how many
% placeholders a value-producing comparison must have bound first.
%   Mode   id of a comparison with at least one output (relation_output_mode),
%          such as "V2 = V0 + V1" declared with V2 as output.
%   Count  number of its variable placeholders that are not outputs.
% Consumed by legality/flow/closure.lp for both flow readiness and ASP
% readiness of the relation.
relation_input_count(Mode, Count) :-
    relation_output_mode(Mode),
    Count = #count {
        Arg : mode_variable_arg(Mode, Arg),
              not mode_arg_direction(Mode, Arg, output)
    }.
