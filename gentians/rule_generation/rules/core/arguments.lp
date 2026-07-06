% Literal argument assignment.
%
% This file expands each selected literal into argument positions, chooses one
% generated variable for each position, and exposes the declared type of each
% argument position.
%
% Shared atom shapes used here:
% - mode(Section,Mode,Pred,Arity,Recall): Python fact. Arity is number of args.
% - mode_arg_type(Mode,Arg,Type): Python fact. Type is any/numeric/etc. for
%   argument Arg of mode Mode.
% - selected(Section,Slot,Mode): defined in core/slots.lp. Section is head/body;
%   Slot is occupied slot id; Mode is selected generator mode id.
% - var(Var): defined in core/slots.lp. Var is an allowed generated variable id.

#defined mode/5.
#defined mode_arg_type/3.

% Rule: derive every argument position for every selected literal.
% Section is head/body. Slot is occupied slot id. Mode is selected mode id.
% Arity comes from mode. Arg ranges from 0 to Arity-1.
arg(Section,Slot,Arg):-
    selected(Section,Slot,Mode),
    mode(Section,Mode,_,Arity,_),
    Arg = 0..Arity-1.

% Choice rule: assign exactly one generated variable to each argument position.
% Section/Slot/Arg identifies one literal argument. Var ranges over var(Var).
% The 1..1 bounds force every argument to be filled and prevent ambiguous
% duplicate assignments for the same argument.
1 { var_at(Section,Slot,Arg,Var) : var(Var) } 1:- arg(Section,Slot,Arg).

% Rule: expose declared argument type at concrete selected positions.
% Type comes from mode_arg_type(Mode,Arg,Type). Downstream typing and numeric
% domain pruning use arg_type(Section,Slot,Arg,Type).
arg_type(Section,Slot,Arg,Type):-
    selected(Section,Slot,Mode),
    mode_arg_type(Mode,Arg,Type).
