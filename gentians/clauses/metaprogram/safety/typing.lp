% Argument type safety.
%
% This file rejects candidates where the same generated variable is placed into
% two argument positions with incompatible declared types.
%
% Shared atom shapes used here:
% - var_at(Section,Slot,Arg,Var): concrete variable assignment for one literal
%   argument. Section is head/body; Slot is slot id; Arg is argument index; Var
%   is generated variable id.
% - arg_type(Section,Slot,Arg,Type): declared non-any type for that concrete
%   argument position, from core/arguments.lp. Missing arg_type means any.

same_variable_scope(Section,Slot,A0,Section,Slot,A1,Var):-
    var_at(Section,Slot,A0,Var),
    var_at(Section,Slot,A1,Var).

same_variable_scope(S0,L0,A0,S1,L1,A1,Var):-
    var_at(S0,L0,A0,Var),
    var_at(S1,L1,A1,Var),
    not conditional_local_at(S0,L0,A0).

same_variable_scope(S0,L0,A0,S1,L1,A1,Var):-
    var_at(S0,L0,A0,Var),
    var_at(S1,L1,A1,Var),
    not conditional_local_at(S1,L1,A1).

% Constraint: a generated variable may not mix two concrete non-any types
% inside one scope. Separate conditional-local scopes may reuse its name.
% Section0/Slot0/Arg0 and Section1/Slot1/Arg1 are two typed argument positions
% using the same Var. Type0 and Type1 are specific declared types. If they
% differ, no single rendered ASP variable can satisfy both domains.
:- same_variable_scope(Section0,Slot0,Arg0,Section1,Slot1,Arg1,Var),
    arg_type(Section0,Slot0,Arg0,Type0),
    arg_type(Section1,Slot1,Arg1,Type1),
    Type0 != Type1.
