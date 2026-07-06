% Argument type safety.
%
% This file rejects candidates where the same generated variable is placed into
% two argument positions with incompatible declared types.
%
% Shared atom shapes used here:
% - var_at(Section,Slot,Arg,Var): concrete variable assignment for one literal
%   argument. Section is head/body; Slot is slot id; Arg is argument index; Var
%   is generated variable id.
% - arg_type(Section,Slot,Arg,Type): declared type for that concrete argument
%   position, from core/arguments.lp. Type any is compatible with every type.

% Constraint: a generated variable may not mix two concrete non-any types.
% Section0/Slot0/Arg0 and Section1/Slot1/Arg1 are two argument positions using
% the same Var. Type0 and Type1 are their declared types. If both are specific
% and different, no single rendered ASP variable can satisfy both domains.
:- var_at(Section0,Slot0,Arg0,Var),
    var_at(Section1,Slot1,Arg1,Var),
    arg_type(Section0,Slot0,Arg0,Type0),
    arg_type(Section1,Slot1,Arg1,Type1),
    Type0 != any,
    Type1 != any,
    Type0 != Type1.
