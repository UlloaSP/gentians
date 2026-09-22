% Structural relations shared by duplicate, property and safety checks.
% same_term_bindings requires the same recursive term shape as well as variable ids;
% matching variables alone would conflate different constants or functors.
% Pair relations exclude a slot compared with itself.


different_variable_binding(Section0, Slot0, Section1, Slot1) :-
    selected(Section0, Slot0, Mode0),
    selected(Section1, Slot1, Mode1),
    mode_variable_arg(Mode0, Arg),
    mode_variable_arg(Mode1, Arg),
    var_at(Section0, Slot0, Arg, Var0),
    var_at(Section1, Slot1, Arg, Var1),
    Var0 != Var1.

same_term_bindings(Section0, Slot0, Section1, Slot1) :-
    selected(Section0, Slot0, Mode0),
    selected(Section1, Slot1, Mode1),
    Section0 != Section1,
    mode_shape(Mode0, Shape),
    mode_shape(Mode1, Shape),
    not different_variable_binding(Section0, Slot0, Section1, Slot1).

same_term_bindings(Section, Slot0, Section, Slot1) :-
    selected(Section, Slot0, Mode0),
    selected(Section, Slot1, Mode1),
    Slot0 != Slot1,
    mode_shape(Mode0, Shape),
    mode_shape(Mode1, Shape),
    not different_variable_binding(Section, Slot0, Section, Slot1).

reversed_binary_vars(Section0, Slot0, Section1, Slot1) :-
    Section0 != Section1,
    var_at(Section0, Slot0, 0, Left),
    var_at(Section0, Slot0, 1, Right),
    var_at(Section1, Slot1, 0, Right),
    var_at(Section1, Slot1, 1, Left).

reversed_binary_vars(Section, Slot0, Section, Slot1) :-
    Slot0 != Slot1,
    var_at(Section, Slot0, 0, Left),
    var_at(Section, Slot0, 1, Right),
    var_at(Section, Slot1, 0, Right),
    var_at(Section, Slot1, 1, Left).

var_in_slot(Section, Slot, Var) :-
    var_at(Section, Slot, _, Var).

positive_body_var_outside_slot(Slot, Var) :-
    body_slot(Slot),
    positive_body_literal(OtherSlot, _, _, _),
    OtherSlot != Slot,
    var_at(body, OtherSlot, _, Var).

var_used_outside_body_slot(Slot, Var) :- body_slot(Slot), var_at(head, _, _, Var).

var_used_outside_body_slot(Slot, Var) :-
    body_slot(Slot),
    var_at(body, OtherSlot, _, Var),
    OtherSlot != Slot.
