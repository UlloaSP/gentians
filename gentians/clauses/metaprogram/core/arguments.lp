% Literal argument assignment.
%
% This file expands each selected literal into its variable argument positions,
% chooses one generated variable for each, and exposes their declared types.
% Fixed terms are encoded in mode_shape/2 and need no variable assignment.
%
% Shared atom shapes used here:
% - mode(Section,Mode,Pred,Arity,Recall): Python fact. Arity is the rendered
%   literal's outer argument count.
% - mode_arg_type(Mode,Arg,Type): Python fact. Type is the declared type such as
%   numeric for variable argument Arg of mode Mode.
% - selected(Section,Slot,Mode): defined in core/slots.lp. Section is head/body;
%   Slot is occupied slot id; Mode is selected generator mode id.
% - var(Var): defined in core/slots.lp. Var is an allowed generated variable id.

% Python fact contract:
% - mode(Section,Mode,Pred,Arity,Recall): emitted by Python for every mode.
%   Arity describes rendered syntax; mode_variable_arg/2 defines bindable slots.
% - mode_variable_arg(Mode,Arg): emitted for each variable placeholder.
% - mode_arg_type(Mode,Arg,Type): emitted for variable argument types.
% Python fact detail: mode(Section,Mode,Pred,Arity,Recall) is emitted per clause mode; Section=head/body, Mode=id, Pred=predicate id for normal modes, Arity=argument count, Recall=mode cap.
#defined mode/5.
% Python fact detail: mode_arg_type(Mode,Arg,Type) gives declared type for zero-based argument Arg of mode Mode.
#defined mode_arg_type/3.
#defined mode_variable_arg/2.

% Rule: derive every variable argument position for every selected literal.
% Section is head/body. Slot is occupied slot id. Mode is selected mode id.
% Arg is a flattened variable-placeholder index.
arg(Section,Slot,Arg):-
    selected(Section,Slot,Mode),
    mode_variable_arg(Mode,Arg).

% Choice rule: assign exactly one generated variable to each variable position.
% Section/Slot/Arg identifies one literal argument. Var ranges over var(Var).
% The 1..1 bounds force every argument to be filled and prevent ambiguous
% duplicate assignments for the same argument.
1 { var_at(Section,Slot,Arg,Var) : var(Var) } 1:- arg(Section,Slot,Arg).

% Rule: expose each declared variable type at concrete selected positions.
% Downstream typing and numeric-domain pruning consume this relation.
arg_type(Section,Slot,Arg,Type):-
    selected(Section,Slot,Mode),
    mode_arg_type(Mode,Arg,Type).
