% Structural relations shared by duplicate, property and safety checks.
% same_term_bindings requires the same recursive term shape as well as variable ids;
% matching variables alone would conflate different constants or functors.
% Pair relations exclude a slot compared with itself.


% DEFINITION, local helper. selected_shape(Section, Slot, Shape): recursive
% argument shape of the unique mode selected at this slot.
%   Section, Slot  an occupied head or body slot.
%   Shape          mode_shape of its selected mode, excluding predicate/sign.
% Project once before comparing slots: many modes share the same shape, so
% joining selected modes in every comparison would ground their Cartesian
% product. Used only by the binding comparisons below.
selected_shape(Section, Slot, Shape) :-
    selected(Section, Slot, Mode), mode_shape(Mode, Shape).

% DEFINITION, local helper. different_variable_binding(Section0, Slot0,
% Section1, Slot1): two selected literals of equal term shape disagree at
% some placeholder.
%   Section0, Slot0  first selected literal.
%   Section1, Slot1  a different selected literal whose mode has the same
%                    mode_shape, hence the same placeholder positions.
% Holds when some placeholder carries different variable ids, as position 1
% of p(V0,V1) and p(V0,V2). Every placeholder holds exactly one variable, so
% "the second literal does not hold Var there" says the two ids differ
% without grounding every pair of ids. Used only, negated, by
% same_term_bindings below, which asks about exactly these pairs.
% Every true var_at belongs to a placeholder of the unique selected mode,
% by representation/arguments.lp, so it already implies mode_variable_arg.
different_variable_binding(Section0, Slot0, Section1, Slot1) :-
    selected_shape(Section0, Slot0, Shape),
    selected_shape(Section1, Slot1, Shape),
    (Section0, Slot0) != (Section1, Slot1),
    var_at(Section0, Slot0, Arg, Var),
    not var_at(Section1, Slot1, Arg, Var).

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
    selected_shape(Section0, Slot0, Shape),
    selected_shape(Section1, Slot1, Shape),
    Section0 != Section1,
    not different_variable_binding(Section0, Slot0, Section1, Slot1).

% DEFINITION, reusable. Same arguments; predicate and polarity are not compared.
% Case 2: both literals are in the same section, at different slots. It holds
% in both slot orders.
same_term_bindings(Section, Slot0, Section, Slot1) :-
    selected_shape(Section, Slot0, Shape),
    selected_shape(Section, Slot1, Shape),
    Slot0 != Slot1,
    not different_variable_binding(Section, Slot0, Section, Slot1).

% DEFINITION, reusable. var_used_outside_body_slot(Slot, Var): Var occurs
% somewhere other than in body Slot.
%   Slot  any body slot, occupied or not; the slot being excluded.
%   Var   variable id with an occurrence outside that slot.
% Shared by pruning/policies/aggregates.lp (an aggregate result must be used)
% and pruning/properties/subsumption.lp (a removed literal must not move a
% variable the rest of the clause needs).
% Case 1: any head occurrence.
var_used_outside_body_slot(Slot, Var) :- body_slot(Slot), var_at(head, _, _, Var).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: an occurrence in a different body slot, whatever literal holds it.
var_used_outside_body_slot(Slot, Var) :-
    body_slot(Slot),
    var_at(body, OtherSlot, _, Var),
    OtherSlot != Slot.
