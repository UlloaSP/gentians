% Tuple and slot helper predicates.
%
% This file contains small structural relations reused by many property
% modules.  It does not reject candidates directly; it names common situations
% such as "these two literals have the same terms" or "this variable occurs
% in another positive body literal".
%
% Shared atom shapes used here:
% - selected(Section,Slot,Mode): defined in core/slots.lp.
% - mode(Section,Mode,Pred,Arity,Recall): Python fact. Arity is compared.
% - var_at(Section,Slot,Arg,Var): defined in core/arguments.lp.
% - body_slot(Slot): defined in core/slots.lp.
% - positive_body_literal(Slot,Mode,Pred,Arity): core/literals.lp alias.

% Rule: two distinct selected literals use the same full term tuple.
% Section0/Slot0 and Section1/Slot1 identify the two literals. Mode0/Mode1 are
% selected only to read their arity. The two mode arities must be equal. The
% Variable positions must share the same generated variable, constant positions
% must contain the same ground term, and kinds must match. Same-slot self-pairs
% are excluded because callers never consume them.
different_term(Section0,Slot0,Section1,Slot1):-
    selected(Section0,Slot0,Mode0),
    selected(Section1,Slot1,Mode1),
    mode_variable_arg(Mode0,Arg),
    mode_variable_arg(Mode1,Arg),
    var_at(Section0,Slot0,Arg,Var0),
    var_at(Section1,Slot1,Arg,Var1),
    Var0 != Var1.

different_term(Section0,Slot0,Section1,Slot1):-
    selected(Section0,Slot0,Mode0),
    selected(Section1,Slot1,Mode1),
    mode_constant_arg(Mode0,Arg,Value0),
    mode_constant_arg(Mode1,Arg,Value1),
    Value0 != Value1.

different_term(Section0,Slot0,Section1,Slot1):-
    selected(Section0,Slot0,Mode0),
    selected(Section1,Slot1,Mode1),
    mode_variable_arg(Mode0,Arg),
    mode_constant_arg(Mode1,Arg,_).

different_term(Section0,Slot0,Section1,Slot1):-
    selected(Section0,Slot0,Mode0),
    selected(Section1,Slot1,Mode1),
    mode_constant_arg(Mode0,Arg,_),
    mode_variable_arg(Mode1,Arg).

same_vars(Section0,Slot0,Section1,Slot1):-
    selected(Section0,Slot0,Mode0),
    selected(Section1,Slot1,Mode1),
    Section0 != Section1,
    mode(Section0,Mode0,_,Arity,_),
    mode(Section1,Mode1,_,Arity,_),
    not different_term(Section0,Slot0,Section1,Slot1).

same_vars(Section,Slot0,Section,Slot1):-
    selected(Section,Slot0,Mode0),
    selected(Section,Slot1,Mode1),
    Slot0 != Slot1,
    mode(Section,Mode0,_,Arity,_),
    mode(Section,Mode1,_,Arity,_),
    not different_term(Section,Slot0,Section,Slot1).

% Rule: two distinct binary literals use reversed variables.
% Section0/Slot0 has arguments Left,Right. Section1/Slot1 has Right,Left.
% Callers ensure the compared literals have arity 2 when needed. Same-slot
% self-pairs are excluded because callers never consume them.
reversed_binary_vars(Section0,Slot0,Section1,Slot1):-
    Section0 != Section1,
    var_at(Section0,Slot0,0,Left),
    var_at(Section0,Slot0,1,Right),
    var_at(Section1,Slot1,0,Right),
    var_at(Section1,Slot1,1,Left).

reversed_binary_vars(Section,Slot0,Section,Slot1):-
    Slot0 != Slot1,
    var_at(Section,Slot0,0,Left),
    var_at(Section,Slot0,1,Right),
    var_at(Section,Slot1,0,Right),
    var_at(Section,Slot1,1,Left).

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
