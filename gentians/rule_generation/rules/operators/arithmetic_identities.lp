% Arithmetic identity pruning.
%
% This file removes redundant arithmetic combinations that express the same
% algebraic relationship more than once, especially add/sub inverse pairs.
%
% Shared atom shapes used here:
% - prune_arithmetic_identities: Python fact enabling this pruning.
% - add_mode(Mode): Python fact. Mode renders as addition.
% - sub_mode(Mode): Python fact. Mode renders as subtraction.
% - selected(body,Slot,Mode): selected body arithmetic literal.
% - var_at(body,Slot,Arg,Var): arithmetic argument assignment. Args 0 and 1 are
%   operands; Arg 2 is result.

#defined prune_arithmetic_identities/0.
#defined add_mode/1.
#defined sub_mode/1.

% Constraint: reject duplicated addition with swapped operands and same result.
% Slot0 and Slot1 use the same add Mode, ordered by Slot0 < Slot1. Slot0 encodes
% Left+Right=Result and Slot1 encodes Right+Left=Result. Addition commutativity
% makes the second literal redundant.
:- prune_arithmetic_identities,
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    add_mode(Mode),
    Slot0 < Slot1,
    var_at(body,Slot0,0,Left),
    var_at(body,Slot0,1,Right),
    var_at(body,Slot0,2,Result),
    var_at(body,Slot1,0,Right),
    var_at(body,Slot1,1,Left),
    var_at(body,Slot1,2,Result).

% Constraint: reject subtraction inverse of an addition, first operand variant.
% AddSlot encodes Left+Right=Result. SubSlot encodes Result-Left=Right. The
% subtraction follows directly from the addition, so keeping both is redundant.
:- prune_arithmetic_identities,
    selected(body,AddSlot,AddMode),
    selected(body,SubSlot,SubMode),
    add_mode(AddMode),
    sub_mode(SubMode),
    var_at(body,AddSlot,0,Left),
    var_at(body,AddSlot,1,Right),
    var_at(body,AddSlot,2,Result),
    var_at(body,SubSlot,0,Result),
    var_at(body,SubSlot,1,Left),
    var_at(body,SubSlot,2,Right).

% Constraint: reject subtraction inverse of an addition, second operand variant.
% AddSlot encodes Left+Right=Result. SubSlot encodes Result-Right=Left. This is
% the symmetric inverse of the same addition fact and is redundant.
:- prune_arithmetic_identities,
    selected(body,AddSlot,AddMode),
    selected(body,SubSlot,SubMode),
    add_mode(AddMode),
    sub_mode(SubMode),
    var_at(body,AddSlot,0,Left),
    var_at(body,AddSlot,1,Right),
    var_at(body,AddSlot,2,Result),
    var_at(body,SubSlot,0,Result),
    var_at(body,SubSlot,1,Right),
    var_at(body,SubSlot,2,Left).
