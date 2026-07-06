% ASP safety for generated variables.
%
% This file approximates the safety conditions needed by rendered ASP rules.
% Variables in heads, negated literals, comparisons, and arithmetic operands
% must be supported by a positive body literal or by safe arithmetic results.
%
% Shared atom shapes used here:
% - comparison_mode(Mode): Python fact for comparison operator modes.
% - arithmetic_mode(Mode): Python fact for arithmetic operator modes.
% - positive_body_literal/4 and negative_body_literal/4: core/literals.lp.
% - selected(body,Slot,Mode): selected body literal.
% - var_at(Section,Slot,Arg,Var): concrete variable assignment.
% - body_slot(Slot): body slot domain.

#defined comparison_mode/1.
#defined arithmetic_mode/1.

% Rule: variables in positive normal body literals are safe.
% Slot is a positive body predicate literal. Mode/Pred/Arity identify it, but
% only Slot is used to collect every Var assigned to that literal.
normal_positive_body_var(Var):-
    positive_body_literal(Slot,Mode,_,_),
    var_at(body,Slot,_,Var).

% Rule: any variable from a positive normal body literal is safe.
% Var is safe if normal_positive_body_var(Var) holds.
safe_var(Var):- normal_positive_body_var(Var).

% Rule: collect variables that appear in the head.
% Var is unsafe unless safe_var(Var) can also be proven.
head_var(Var):- var_at(head,_,_,Var).

% Rule: collect variables that appear under default negation.
% Slot is a negative normal body literal. Var is each variable used by it.
negated_var(Var):-
    negative_body_literal(Slot,Mode,_,_),
    var_at(body,Slot,_,Var).

% Rule: collect variables used by comparison operators.
% Slot is a selected body comparison. Mode is the comparison mode id. Var is
% either comparison argument.
comparison_var(Var):-
    selected(body,Slot,Mode),
    comparison_mode(Mode),
    var_at(body,Slot,_,Var).

% Rule: collect arithmetic operand variables.
% Slot is a selected arithmetic body literal. Arg ranges over operands 0 and 1.
% Var is the variable used as an arithmetic input.
arithmetic_operand_var(Var):-
    selected(body,Slot,Mode),
    arithmetic_mode(Mode),
    Arg = 0..1,
    var_at(body,Slot,Arg,Var).

% Rule: an arithmetic result is safe only when both operands are already safe.
% Slot is an arithmetic literal. Left and Right are variables at operands 0 and
% 1. If both safe_var(Left) and safe_var(Right), the result at argument 2 may
% become safe.
arithmetic_result_safe(Slot):-
    selected(body,Slot,Mode),
    arithmetic_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    safe_var(Left),
    safe_var(Right).

% Rule: safe arithmetic result variables.
% Slot is an arithmetic literal proven safe by arithmetic_result_safe. Var is
% argument 2, the rendered result of the arithmetic expression.
safe_var(Var):-
    arithmetic_result_safe(Slot),
    var_at(body,Slot,2,Var).

% Rule: Var is used outside body Slot if it appears in any head literal.
% Used to require arithmetic results and aggregate results to be consumed.
var_used_outside_body_slot(Slot,Var):- body_slot(Slot), var_at(head,_,_,Var).

% Rule: Var is used outside body Slot if it appears in another body slot.
% OtherSlot must differ from Slot. The same slot does not count as consumption.
var_used_outside_body_slot(Slot,Var):-
    body_slot(Slot),
    var_at(body,OtherSlot,_,Var),
    OtherSlot != Slot.

% Constraint: arithmetic result variables must be consumed elsewhere.
% Slot is an arithmetic literal. Var is argument 2, the result variable. If Var
% appears only in that arithmetic literal, the expression has no effect.
:- selected(body,Slot,Mode),
    arithmetic_mode(Mode),
    var_at(body,Slot,2,Var),
    not var_used_outside_body_slot(Slot,Var).

% Constraint: every head variable must be safe.
% Var appears in the head and must be grounded by a positive body source.
:- head_var(Var), not safe_var(Var).

% Constraint: every negated-literal variable must be safe.
% Default-negated atoms in ASP cannot introduce new variables.
:- negated_var(Var), not safe_var(Var).

% Constraint: every comparison variable must be safe.
% Comparison operators cannot introduce new variables in ASP.
:- comparison_var(Var), not safe_var(Var).

% Constraint: every arithmetic operand variable must be safe.
% Arithmetic expressions cannot introduce operand variables.
:- arithmetic_operand_var(Var), not safe_var(Var).
