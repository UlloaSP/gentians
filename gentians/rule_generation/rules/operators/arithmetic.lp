% Arithmetic operator pruning.
%
% This file handles generated arithmetic literals. It rejects result variables
% reused as operands, canonicalizes commutative/symmetric arithmetic operands,
% and rejects duplicate computations that bind different result variables.
%
% Shared atom shapes used here:
% - arithmetic_mode(Mode): derived atom. Mode renders as arithmetic expression.
% - add_mode(Mode), mul_mode(Mode), div_mode(Mode),
%   mod_mode(Mode), abs_mode(Mode): Python facts for arithmetic operator
%   families.
% - selected(body,Slot,Mode): selected body arithmetic literal.
% - var_at(body,Slot,Arg,Var): arithmetic argument assignment. Args 0 and 1 are
%   operands; Arg 2 is the result variable.

% Python fact contract:
% - add_mode(Mode): emitted by Python for addition modes.
% - mul_mode(Mode): emitted by Python for multiplication modes.
% - div_mode(Mode): emitted by Python for division modes.
% - mod_mode(Mode): emitted by Python for modulo modes.
% - abs_mode(Mode): emitted by Python for absolute-distance modes.
% Python fact detail: add_mode(Mode) marks arithmetic modes rendered as addition.
#defined add_mode/1.
% Python fact detail: mul_mode(Mode) marks arithmetic modes rendered as multiplication.
#defined mul_mode/1.
% Python fact detail: div_mode(Mode) marks arithmetic modes rendered as division.
#defined div_mode/1.
% Python fact detail: mod_mode(Mode) marks arithmetic modes rendered as modulo.
#defined mod_mode/1.
% Python fact detail: abs_mode(Mode) marks arithmetic modes rendered as absolute distance.
#defined abs_mode/1.

% Rule: addition modes are arithmetic modes.
% Mode is the Python id for an arithmetic body literal rendered with +.
arithmetic_mode(Mode):- add_mode(Mode).

% Rule: multiplication modes are arithmetic modes.
% Mode is the Python id for an arithmetic body literal rendered with *.
arithmetic_mode(Mode):- mul_mode(Mode).

% Rule: division modes are arithmetic modes.
% Mode is the Python id for an arithmetic body literal rendered with /.
arithmetic_mode(Mode):- div_mode(Mode).

% Rule: modulo modes are arithmetic modes.
% Mode is the Python id for an arithmetic body literal rendered with \.
arithmetic_mode(Mode):- mod_mode(Mode).

% Rule: absolute-distance modes are arithmetic modes.
% Mode is the Python id for an arithmetic body literal rendered as |X-Y|=Z.
arithmetic_mode(Mode):- abs_mode(Mode).

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
% and 1. Descending variable order is rejected.
:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

% Constraint: canonicalize multiplication operands.
% Multiplication is commutative. Left and Right are operand variables at
% arguments 0 and 1. Descending variable order is redundant.
:- selected(body,Slot,Mode),
    mul_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

% Constraint: canonicalize abs-distance operands.
% The rendered abs mode represents |Left-Right|=Result, symmetric in Left and
% Right. Descending variable order is redundant.
:- selected(body,Slot,Mode),
    abs_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

% Rule: adjacent same-mode arithmetic slots differ in at least one operand.
% Equal modes are contiguous; duplicate-input checks only query adjacent pairs.
arithmetic_input_differs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    arithmetic_mode(Mode),
    Slot1 = Slot0 + 1,
    Arg = 0..1,
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    Left != Right.

% Rule: adjacent arithmetic slots have identical inputs.
% Equal modes are contiguous and tuple-sorted, so equal inputs form adjacent
% runs. If no operand difference is found, both literals compute the same value.
same_arithmetic_inputs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    arithmetic_mode(Mode),
    Slot1 = Slot0 + 1,
    not arithmetic_input_differs(Slot0,Slot1).

% Constraint: identical arithmetic computations must bind same result variable.
% Result0 and Result1 are argument 2 of same-input arithmetic literals. Different
% result variables duplicate one computed value.
:- same_arithmetic_inputs(Slot0,Slot1),
    var_at(body,Slot0,2,Result0),
    var_at(body,Slot1,2,Result1),
    Result0 != Result1.

% Two equations 2*Left=Result and 2*Right=Result contain a removable common
% factor. A mixed pair such as Left+Left=Result and Left+Right=Result expresses
% the same equality without scaling.
:- selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    add_mode(Mode),
    Slot0 < Slot1,
    var_at(body,Slot0,0,Left),
    var_at(body,Slot0,1,Left),
    var_at(body,Slot0,2,Result),
    var_at(body,Slot1,0,Right),
    var_at(body,Slot1,1,Right),
    var_at(body,Slot1,2,Result),
    normal_positive_body_var(Left),
    normal_positive_body_var(Right),
    Left != Right.
