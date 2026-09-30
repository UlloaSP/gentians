% Structural relations shared by duplicate, property and safety checks.
% same_term_bindings requires the same recursive term shape as well as variable ids;
% matching variables alone would conflate different constants or functors.
% Pair relations exclude a slot compared with itself.


% DEFINITION, local helper. different_variable_binding(Section0, Slot0,
% Section1, Slot1): two selected literals disagree at some shared placeholder.
%   Section0, Slot0  first selected literal.
%   Section1, Slot1  second selected literal.
% Holds when a placeholder position that both modes have carries different
% variable ids, as position 1 of p(V0,V1) and p(V0,V2). Used only, negated, by
% same_term_bindings below.
different_variable_binding(Section0, Slot0, Section1, Slot1) :-
    selected(Section0, Slot0, Mode0),
    selected(Section1, Slot1, Mode1),
    mode_variable_arg(Mode0, Arg),
    mode_variable_arg(Mode1, Arg),
    var_at(Section0, Slot0, Arg, Var0),
    var_at(Section1, Slot1, Arg, Var1),
    Var0 != Var1.

% DEFINITION, reusable. same_term_bindings(Section0, Slot0, Section1, Slot1):
% two different selected literals have the same arguments.
%   Section0, Slot0  first selected literal.
%   Section1, Slot1  second selected literal.
% "Same arguments" means equal mode_shape (same nesting, functors and
% constants) and equal variable ids at every placeholder. Predicate and
% polarity are NOT compared: p(V0,V1) and "not q(V0,V1)" satisfy it, and each
% consumer adds the predicate relation it needs. Shared by
% pruning/redundancy/literals.lp and tautologies.lp and by
% pruning/properties/implies.lp, mutex.lp, equivalent.lp, complement.lp,
% partition.lp and subsumption.lp.
% Case 1: the literals are in different sections (one head, one body).
same_term_bindings(Section0, Slot0, Section1, Slot1) :-
    selected(Section0, Slot0, Mode0),
    selected(Section1, Slot1, Mode1),
    Section0 != Section1,
    mode_shape(Mode0, Shape),
    mode_shape(Mode1, Shape),
    not different_variable_binding(Section0, Slot0, Section1, Slot1).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: both literals are in the same section, at different slots. It holds
% in both slot orders.
same_term_bindings(Section, Slot0, Section, Slot1) :-
    selected(Section, Slot0, Mode0),
    selected(Section, Slot1, Mode1),
    Slot0 != Slot1,
    mode_shape(Mode0, Shape),
    mode_shape(Mode1, Shape),
    not different_variable_binding(Section, Slot0, Section, Slot1).

% DEFINITION, reusable. reversed_binary_vars(Section, Slot0, Section, Slot1):
% two literals of the same section hold the same two variables, swapped.
%   Section  head or body, the same for both literals.
%   Slot0    slot of a literal with variables (Left, Right) at positions 0, 1.
%   Slot1    a different slot, with (Right, Left) at positions 0, 1.
% Example: p(V0,V1) and q(V1,V0). Predicates are not compared. Consumed by
% pruning/properties/inverse.lp.
reversed_binary_vars(Section, Slot0, Section, Slot1) :-
    Slot0 != Slot1,
    var_at(Section, Slot0, 0, Left),
    var_at(Section, Slot0, 1, Right),
    var_at(Section, Slot1, 0, Right),
    var_at(Section, Slot1, 1, Left).

% DEFINITION, reusable. var_in_slot(Section, Slot, Var): Var occurs in the
% literal at that slot.
%   Section, Slot  the selected literal.
%   Var            variable id at any of its placeholders.
% Drops the position. Consumed by pruning/properties/subsumption.lp.
var_in_slot(Section, Slot, Var) :-
    var_at(Section, Slot, _, Var).

% DEFINITION, currently unused. positive_body_var_outside_slot(Slot, Var): a
% positive plain body atom other than the one at Slot mentions Var.
%   Slot  any body slot, occupied or not; the slot being excluded.
%   Var   variable id of a positive body atom at a different slot.
% No module consumes this view at present.
positive_body_var_outside_slot(Slot, Var) :-
    body_slot(Slot),
    positive_body_literal(OtherSlot, _, _, _),
    OtherSlot != Slot,
    var_at(body, OtherSlot, _, Var).

% DEFINITION, reusable. var_used_outside_body_slot(Slot, Var): Var occurs
% somewhere other than in body Slot.
%   Slot  any body slot, occupied or not; the slot being excluded.
%   Var   variable id with an occurrence outside that slot.
% Shared by pruning/policies/aggregates.lp (an aggregate result must be used)
% and pruning/properties/subsumption.lp (a removed literal must not lose a
% join).
% Case 1: any head occurrence.
var_used_outside_body_slot(Slot, Var) :- body_slot(Slot), var_at(head, _, _, Var).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: an occurrence in a different body slot, whatever literal holds it.
var_used_outside_body_slot(Slot, Var) :-
    body_slot(Slot),
    var_at(body, OtherSlot, _, Var),
    OtherSlot != Slot.
