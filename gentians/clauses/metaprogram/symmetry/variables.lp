% Choose dense variable ids ordered by their first occurrence.
% These comparisons order syntactic ids, not their object-level values.

% DEFINITION, local helper. potential_var_pos(body, Slot, Arg): a variable
% placeholder that some declared body mode could place at this slot.
%   Slot  any available body slot, including an unoccupied one.
%   Arg   an actual mode_variable_arg position, not a predicate arity index.
% The union across modes overapproximates actual positions. Constants do not
% add positions, and gaps in placeholder indexes are not counted as bindings.
% Used only by first_occurrence_bound below.
potential_var_pos(body, Slot, Arg) :-
    body_slot(Slot), mode_section(Mode, body), mode_variable_arg(Mode, Arg).

% DEFINITION, local helper. potential_var_pos(head, Slot, Arg): a variable
% placeholder of a member of some declared complete head form.
%   Slot  the member's position within its head form.
%   Arg   a variable-placeholder position, including variable head guards.
% All forms contribute possible positions, even when another form or no head
% is selected. Used only by first_occurrence_bound below.
potential_var_pos(head, Slot, Arg) :-
    head_form_member(_, Slot, Mode), mode_variable_arg(Mode, Arg).

% DEFINITION, reusable domain bound. first_occurrence_bound(Section, Slot,
% Arg, Bound): largest variable id that could occur at this position under
% the dense, first-occurrence ordering enforced below.
%   Section, Slot, Arg  a possible placeholder, in Clingo's body-before-head
%                       tuple order (not section_order's head-before-body).
%   Bound               number of possible earlier placeholder positions.
% If id V occurs here, ids 0..V-1 have earlier first occurrences. One position
% holds one id, so V cannot exceed the number of possible earlier positions.
% Counting the union of all modes is conservative when slots are empty or
% the selected mode has fewer placeholders. The existing ordering constraints
% still reject impossible assignments inside this overapproximation.
% Consumed by representation/arguments.lp to omit choices that these same
% symmetry rules would reject. This introduces no task limit or new pruning.
first_occurrence_bound(Section, Slot, Arg, Bound) :-
    potential_var_pos(Section, Slot, Arg),
    Bound = #count {
        S, L, A : potential_var_pos(S, L, A), (S, L, A) < (Section, Slot, Arg)
    }.

% CONSTRAINT. Variable ids are used without gaps, starting at 0.
%   Var1  a used variable id.
%   Var0  a smaller id of the domain that is not used.
%   pruned: :- edge(V0,V2).      V1 is skipped
%   kept:   :- edge(V0,V1).
:- used_var(Var1), var(Var0), Var0 < Var1, not used_var(Var0).

% DEFINITION, local helper. first_var_pos(Var, Section, Slot, Arg): where Var
% first occurs.
%   Var      a used variable id.
%   Section  section of its first occurrence.
%   Slot     slot of its first occurrence.
%   Arg      placeholder position of its first occurrence.
% "First" is the minimum of (Section, Slot, Arg) in Clingo's term order, in
% which body < head: a body occurrence precedes every head occurrence. Used
% only by the constraint below.
first_var_pos(Var, Section, Slot, Arg) :-
    used_var(Var),
    (Section, Slot, Arg) = #min{(S, L, A) : var_at(S, L, A, Var)}.

% CONSTRAINT. Ids grow in the order of first occurrence: a smaller id never
% first occurs after a greater one. Renaming variables does not change a
% clause, so one naming per clause is kept.
%   Var0, Var1            two consecutive used ids. Ids have no gaps (see
%                         above), so ordering neighbours orders them all.
%   (S0,L0,A0), (S1,L1,A1)  their first positions.
%   pruned: :- edge(V1,V0).                   V1 occurs before V0
%   kept:   :- edge(V0,V1).
%   kept:   target(V1,V0) :- edge(V0,V1).     the body is read first, so the
%                                             head may list ids in any order
:- first_var_pos(Var0, S0, L0, A0),
    first_var_pos(Var1, S1, L1, A1),
    Var1 = Var0 + 1,
    (S0, L0, A0) > (S1, L1, A1).
