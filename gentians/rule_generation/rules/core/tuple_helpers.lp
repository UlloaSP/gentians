% Tuple and slot helper predicates.
%
% This file contains small structural relations reused by many property
% modules.  It does not reject candidates directly; it names common situations
% such as "these two literals have the same variables" or "this variable occurs
% in another positive body literal".
%
% Shared atom shapes used here:
% - selected(Section,Slot,Mode): defined in core/slots.lp.
% - mode(Section,Mode,Pred,Arity,Recall): Python fact. Arity is compared.
% - var_at(Section,Slot,Arg,Var): defined in core/arguments.lp.
% - body_slot(Slot): defined in core/slots.lp.
% - positive_body_literal(Slot,Mode,Pred,Arity): core/literals.lp alias.

% Rule: two selected literals use the same full variable tuple.
% Section0/Slot0 and Section1/Slot1 identify the two literals. Mode0/Mode1 are
% selected only to read their arity. The two mode arities must be equal. The
% #count equals Arity only when every Arg position uses the same Var in both
% literals.
same_vars(Section0,Slot0,Section1,Slot1):-
    selected(Section0,Slot0,Mode0),
    selected(Section1,Slot1,Mode1),
    mode(Section0,Mode0,_,Arity,_),
    mode(Section1,Mode1,_,Arity,_),
    Arity = #count{Arg : var_at(Section0,Slot0,Arg,Var), var_at(Section1,Slot1,Arg,Var)}.

% Rule: two binary literals use reversed variables.
% Section0/Slot0 has arguments Left,Right. Section1/Slot1 has Right,Left.
% Callers ensure the compared literals have arity 2 when needed.
reversed_binary_vars(Section0,Slot0,Section1,Slot1):-
    var_at(Section0,Slot0,0,Left),
    var_at(Section0,Slot0,1,Right),
    var_at(Section1,Slot1,0,Right),
    var_at(Section1,Slot1,1,Left).

% Rule: Var occurs somewhere in a selected literal slot.
% Section is head/body, Slot is slot id, Var is any generated variable present
% at some argument position in that slot.
var_in_slot(Section,Slot,Var):-
    var_at(Section,Slot,_,Var).

% Rule: Var occurs in another positive body literal outside Slot.
% Slot is the slot being checked. OtherSlot is a different positive normal body
% literal. Var is shared with OtherSlot. Used by property constraints that need
% to know whether a variable is supported outside the current literal.
positive_body_var_outside_slot(Slot,Var):-
    body_slot(Slot),
    positive_body_literal(OtherSlot,_,_,_),
    OtherSlot != Slot,
    var_at(body,OtherSlot,_,Var).
