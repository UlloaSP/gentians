% Positive-body same-predicate subsumption.
%
% This file rejects a general positive body literal when another positive body
% literal of the same predicate is stricter and already subsumes it. It focuses
% on same-predicate literals where the stricter literal adds an equality between
% arguments.
%
% Shared atom shapes used here:
% - positive_body_literal(Slot,Mode,Pred,Arity): selected positive body atom.
% - var_at(body,Slot,Arg,Var): variable assignment.
% - same_vars(body,Slot0,body,Slot1): identical tuple variables.
% - var_used_outside_body_slot(Slot,Var): variable is consumed outside Slot.
% - var_in_slot(body,Slot,Var): Var appears inside Slot.
% - body_slot(Slot): body slot domain.

% Rule: SpecificSlot adds an equality absent from GeneralSlot.
% GeneralSlot and SpecificSlot are positive literals of same Pred/Arity. Arg0
% and Arg1 are two argument positions. SpecificVar appears at both positions in
% SpecificSlot, while GeneralSlot uses different variables GeneralVar0 and
% GeneralVar1. Therefore SpecificSlot is stricter than GeneralSlot.
specific_adds_equality(GeneralSlot,SpecificSlot):-
    positive_body_literal(GeneralSlot,_,Pred,Arity),
    positive_body_literal(SpecificSlot,_,Pred,Arity),
    Arg0 = 0..Arity-1,
    Arg1 = 0..Arity-1,
    Arg0 < Arg1,
    var_at(body,SpecificSlot,Arg0,SpecificVar),
    var_at(body,SpecificSlot,Arg1,SpecificVar),
    var_at(body,GeneralSlot,Arg0,GeneralVar0),
    var_at(body,GeneralSlot,Arg1,GeneralVar1),
    GeneralVar0 != GeneralVar1.

% Rule: GeneralSlot has an equality absent from SpecificSlot.
% This blocks subsumption: GeneralSlot is not more general if it imposes an
% equality that SpecificSlot does not. Arg0/Arg1 are compared positions.
general_has_extra_equality(GeneralSlot,SpecificSlot):-
    positive_body_literal(GeneralSlot,_,Pred,Arity),
    positive_body_literal(SpecificSlot,_,Pred,Arity),
    Arg0 = 0..Arity-1,
    Arg1 = 0..Arity-1,
    Arg0 < Arg1,
    var_at(body,GeneralSlot,Arg0,GeneralVar),
    var_at(body,GeneralSlot,Arg1,GeneralVar),
    var_at(body,SpecificSlot,Arg0,SpecificVar0),
    var_at(body,SpecificSlot,Arg1,SpecificVar1),
    SpecificVar0 != SpecificVar1.

% Rule: a variable needed outside GeneralSlot is not present in SpecificSlot.
% Var occurs in GeneralSlot and is consumed elsewhere by head/body/aggregate
% safety. If SpecificSlot lacks Var, removing GeneralSlot would lose a join, so
% subsumption is unsafe.
general_var_unsupported(GeneralSlot,SpecificSlot):-
    body_slot(SpecificSlot),
    var_at(body,GeneralSlot,_,Var),
    var_used_outside_body_slot(GeneralSlot,Var),
    not var_in_slot(body,SpecificSlot,Var).

% Constraint: reject a subsumed general positive literal.
% GeneralSlot and SpecificSlot are different positive literals with same
% Pred/Arity. They are not identical. SpecificSlot adds at least one equality,
% GeneralSlot adds no equality missing from SpecificSlot, and every external
% variable used by GeneralSlot still appears in SpecificSlot. Then GeneralSlot
% is redundant.
:- positive_body_literal(GeneralSlot,_,Pred,Arity),
    positive_body_literal(SpecificSlot,_,Pred,Arity),
    GeneralSlot != SpecificSlot,
    not same_vars(body,GeneralSlot,body,SpecificSlot),
    specific_adds_equality(GeneralSlot,SpecificSlot),
    not general_has_extra_equality(GeneralSlot,SpecificSlot),
    not general_var_unsupported(GeneralSlot,SpecificSlot).
