% Whether a positive body atom can be removed without breaking directed flow.
%
% Several prunings reject a clause because one of its positive atoms is
% redundant: the clause without that atom means the same and is enumerated on
% its own. That only holds if the shorter clause is in the language. With
% directed modes the redundant atom may be the only producer of a variable:
%   #modeb(1,node(var(t,output))).  #modeb(1,red(var(t,input))).
%   h(V0) :- node(V0), red(V0).     red implies node, so node(V0) is redundant
%   h(V0) :- red(V0).               illegal: nothing binds the input of red
% Rejecting the first clause would leave "h is what is red" unlearnable.
%
% flow_needed(Slot) is a sufficient test, not the exact fixed point without
% the atom: it accepts a removal only when another atom that needs no input
% supplies each variable at least as strongly. When in doubt the atom counts
% as needed and the redundant clause is kept, which is always sound.
%
% This file has no constraint of its own.

% DEFINITION, local helper. mode_needs_input(Mode): literals of Mode wait for
% some input before they supply anything.
%   Mode  id of a template with at least one placeholder declared input.
% Used only, negated, by free_binding_mode below.
mode_needs_input(Mode) :- mode_arg_direction(Mode, _, input).

% DEFINITION, local helper. free_binding_mode(Mode): literals of Mode supply
% their variables unconditionally.
%   Mode  id of a positive plain atom template without input placeholders.
% Such a literal is ready whatever else the clause contains, so what it
% supplies does not depend on the atom being removed. Used only by the two
% views below.
free_binding_mode(Mode) :- binding_mode(Mode), not mode_needs_input(Mode).

% DEFINITION, local helper. produced_without(Slot, Var): some atom other than
% the one at Slot outputs Var unconditionally.
%   Slot  body slot of the atom whose removal is being considered.
%   Var   variable id at an output placeholder of a different body atom of a
%         free binding mode, grounded in every binding alternative.
% Used by bound_without and flow_needed below.
produced_without(Slot, Var) :-
    positive_body_literal(Slot, _, _, _),
    selected(body, Other, Mode),
    Other != Slot,
    free_binding_mode(Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Other, Arg, Var),
    not pooled_body_missing_var(Other, Var).

% DEFINITION, local helper. bound_without(Slot, Var): Var stays bound when the
% atom at Slot is removed.
%   Slot  body slot of the atom whose removal is being considered.
%   Var   variable id still available to feed inputs.
% Used only, negated, by flow_needed below.
% Case 1: another atom outputs it unconditionally.
bound_without(Slot, Var) :- produced_without(Slot, Var).

% DEFINITION, local helper. Same predicate. Case 2: another atom of a free
% binding mode holds it at an "any" placeholder.
bound_without(Slot, Var) :-
    positive_body_literal(Slot, _, _, _),
    selected(body, Other, Mode),
    Other != Slot,
    free_binding_mode(Mode),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Other, Arg, Var),
    not pooled_body_missing_var(Other, Var).

% DEFINITION, local helper. Same predicate. Case 3: it is a head input, bound
% from the start.
bound_without(Slot, Var) :-
    positive_body_literal(Slot, _, _, _),
    head_input_var(Var).

% DEFINITION, reusable. flow_needed(Slot): removing the positive body atom at
% Slot may leave the clause without a producer or binder it needs.
%   Slot  body slot of a positive plain atom.
% Consumed, negated, by every pruning that rejects a clause for containing a
% redundant positive atom: pruning/properties/implies.lp, universal.lp,
% reflexive.lp, project_implies.lp, transitive.lp, inverse.lp and
% subsumption.lp. One definition keeps "this atom may be dropped" in a single
% place.
% Case 1: the atom outputs a variable used elsewhere that no free atom
% outputs.
%   Mode, Arg  its template and an output placeholder.
%   Var        variable id written there and used outside the atom.
flow_needed(Slot) :-
    positive_body_literal(Slot, Mode, _, _),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var),
    var_used_outside_body_slot(Slot, Var),
    not produced_without(Slot, Var).

% DEFINITION, reusable. Same predicate. Case 2: the atom binds, at an "any"
% placeholder, a variable used elsewhere that nothing else binds
% unconditionally.
flow_needed(Slot) :-
    positive_body_literal(Slot, Mode, _, _),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Slot, Arg, Var),
    var_used_outside_body_slot(Slot, Var),
    not bound_without(Slot, Var).
