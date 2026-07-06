% Arithmetic operator pruning.
%
% This file handles generated arithmetic literals. It rejects result variables
% reused as operands, canonicalizes commutative/symmetric arithmetic operands,
% and rejects duplicate computations that bind different result variables.
%
% Shared atom shapes used here:
% - arithmetic_mode(Mode): Python fact. Mode renders as arithmetic expression.
% - add_mode(Mode), mul_mode(Mode), abs_mode(Mode): Python facts for operator
%   families with symmetric inputs in this representation.
% - canonical_prune: Python fact enabling optional canonical pruning.
% - selected(body,Slot,Mode): selected body arithmetic literal.
% - var_at(body,Slot,Arg,Var): arithmetic argument assignment. Args 0 and 1 are
%   operands; Arg 2 is the result variable.

#defined arithmetic_mode/1.
#defined add_mode/1.
#defined mul_mode/1.
#defined abs_mode/1.
#defined canonical_prune/0.

% Constraint: arithmetic result must not be one of its own operands.
% Slot is arithmetic body slot. Operand ranges over 0 and 1. Var appears both
% as an operand and as result argument 2, creating equations like X+Y=X.
:- selected(body,Slot,Mode),
    arithmetic_mode(Mode),
    var_at(body,Slot,Operand,Var),
    Operand = 0..1,
    var_at(body,Slot,2,Var).

% Constraint: canonicalize addition operands.
% Addition is commutative. Left and Right are operand variables at arguments 0
% and 1. Descending variable order is rejected when canonical_prune is enabled.
:- canonical_prune,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

% Constraint: canonicalize multiplication operands.
% Multiplication is commutative. Left and Right are operand variables at
% arguments 0 and 1. Descending variable order is redundant.
:- canonical_prune,
    selected(body,Slot,Mode),
    mul_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

% Constraint: canonicalize abs-distance operands.
% The rendered abs mode represents |Left-Right|=Result, symmetric in Left and
% Right. Descending variable order is redundant.
:- canonical_prune,
    selected(body,Slot,Mode),
    abs_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

% Rule: two same-mode arithmetic slots differ in at least one operand.
% Slot0 and Slot1 use the same arithmetic Mode. Arg is operand 0 or 1. Left and
% Right are variables at that operand position. Different operands mean different
% computations.
arithmetic_input_differs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    arithmetic_mode(Mode),
    Arg = 0..1,
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    Left != Right.

% Rule: two arithmetic slots have identical inputs.
% Slot0 < Slot1 orders the pair. Both slots use the same Mode. If no operand
% difference is found, both arithmetic literals compute the same value.
same_arithmetic_inputs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    arithmetic_mode(Mode),
    Slot0 < Slot1,
    not arithmetic_input_differs(Slot0,Slot1).

% Constraint: identical arithmetic computations must bind same result variable.
% Result0 and Result1 are argument 2 of same-input arithmetic literals. Different
% result variables duplicate one computed value.
:- same_arithmetic_inputs(Slot0,Slot1),
    var_at(body,Slot0,2,Result0),
    var_at(body,Slot1,2,Result1),
    Result0 != Result1.
