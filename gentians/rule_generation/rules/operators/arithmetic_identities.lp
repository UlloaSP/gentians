% Arithmetic identity pruning.
%
% This file removes redundant arithmetic combinations that express the same
% algebraic relationship more than once, specifically add/sub inverse pairs.
%
% Shared atom shapes used here:
% - add_mode(Mode): Python fact. Mode renders as addition.
% - sub_mode(Mode): Python fact. Mode renders as subtraction.
% - selected(body,Slot,Mode): selected body arithmetic literal.
% - var_at(body,Slot,Arg,Var): arithmetic argument assignment. Args 0 and 1 are
%   operands; Arg 2 is result.

% Python fact contract:
% - add_mode(Mode): emitted by Python for addition modes.
% - sub_mode(Mode): emitted by Python for subtraction modes.
% Python fact detail: add_mode(Mode) marks arithmetic modes rendered as addition.
#defined add_mode/1.
% Python fact detail: sub_mode(Mode) marks arithmetic modes rendered as subtraction.
#defined sub_mode/1.

% Constraint: reject subtraction inverse of an addition, first operand variant.
% AddSlot encodes Left+Right=Result. SubSlot encodes Result-Left=Right. The
% subtraction follows directly from the addition, so keeping both is redundant.
:- selected(body,AddSlot,AddMode),
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
:- selected(body,AddSlot,AddMode),
    selected(body,SubSlot,SubMode),
    add_mode(AddMode),
    sub_mode(SubMode),
    var_at(body,AddSlot,0,Left),
    var_at(body,AddSlot,1,Right),
    var_at(body,AddSlot,2,Result),
    var_at(body,SubSlot,0,Result),
    var_at(body,SubSlot,1,Right),
    var_at(body,SubSlot,2,Left).
