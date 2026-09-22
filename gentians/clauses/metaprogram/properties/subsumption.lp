% Positive-body same-predicate subsumption.
%
% This file rejects a general positive body literal when another positive body
% literal of the same predicate is stricter and already subsumes it. It focuses
% on same-predicate literals where the stricter literal adds an equality between
% arguments.

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

% Keep every variable needed outside the general literal; otherwise a join is lost.

general_var_unsupported(GeneralSlot,SpecificSlot):-
    body_slot(SpecificSlot),
    var_at(body,GeneralSlot,_,Var),
    var_used_outside_body_slot(GeneralSlot,Var),
    not var_in_slot(body,SpecificSlot,Var).

:- positive_body_literal(GeneralSlot,_,Pred,Arity),
    positive_body_literal(SpecificSlot,_,Pred,Arity),
    GeneralSlot != SpecificSlot,
    not same_vars(body,GeneralSlot,body,SpecificSlot),
    specific_adds_equality(GeneralSlot,SpecificSlot),
    not general_has_extra_equality(GeneralSlot,SpecificSlot),
    not general_var_unsupported(GeneralSlot,SpecificSlot).
