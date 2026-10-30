% Keep one clause of each set of renamed twins.
%
% Reordering literals of a mode and renaming variables does not change a
% clause, yet symmetry/slots.lp and symmetry/variables.lp only compare
% neighbours. Both of these pass them and mean the same path:
%   h :- p(V0,V1), p(V1,V2).
%   h :- p(V0,V1), p(V2,V0).
% A clause survives only if no symmetry rewrites it into a smaller twin. Twins
% are compared by the positions that share a variable, which needs no renaming:
% a position pair changing from different to shared is what lowers a
% first-occurrence numbering. mode_facts.twin_facts compiles the symmetries that
% recalls allow, and these rules are normal: they propagate during the search,
% so twins are never enumerated and never spend an incremental budget.
%
% The representative is the smallest form, which every other symmetry rule of
% the program keeps. Rules on operand order are not invariant under renaming,
% so a symmetry may also swap the operands of a literal they apply to. Arithmetic
% that only canonicalization can equate, such as mirrored comparisons of two
% modes, stays for canonicalization.

% DEFINITION, local helper. twin_ordered_aggregate(Mode): symmetry/aggregates.lp
% orders variables of this aggregate by id, so a twin can be illegal in a way no
% operand swap repairs. Comparing it could reject a clause for a twin that does
% not exist. A #sum compares only non-weight arguments, so it needs three.
%   Mode  an aggregate template with interchangeable arguments.
% Case 1: the tuple of a #count.
twin_ordered_aggregate(Mode) :- count_aggregate_mode(Mode), interchangeable_tuple_args(Mode, _, _).
% Same predicate. Case 2: the condition of a #count.
twin_ordered_aggregate(Mode) :- count_aggregate_mode(Mode), interchangeable_condition_args(Mode, 0, _, _).
% Same predicate. Case 3: the condition of a #sum beyond its weight.
twin_ordered_aggregate(Mode) :-
    sum_aggregate_mode(Mode), aggregate_shape(Mode, Arity, 1), Arity >= 3,
    interchangeable_condition_args(Mode, 0, _, _).

% DEFINITION, local helper. twin_compared_mode(Mode): this mode takes part in
% twins; a fixed mode has local scopes that a symmetry cannot read.
%   Mode  a declared mode.
% Used by twin_literal and twin_same_mode below.
twin_compared_mode(Mode) :-
    mode_section(Mode, _), not twin_fixed_mode(Mode), not twin_ordered_aggregate(Mode).

% DEFINITION, local helper. twin_literal(Section, Slot): this literal takes part
% in comparisons. An uncompared literal never rejects a clause: whatever twin it
% has, the compared literals of that twin stay legal.
%   Section, Slot  a selected literal.
% Used only by twin_var below.
twin_literal(body, Slot) :- selected(body, Slot, Mode), twin_compared_mode(Mode).
twin_literal(head, Slot) :- selected(head, Slot, _).

% DEFINITION, local helper. twin_var(Position, Var): Var occurs at Position.
%   Position  a compiled placeholder of a compared literal.
%   Var       the variable id written there.
% Used only by twin_same below.
twin_var(Position, Var) :-
    twin_position(Position, Section, Slot, Arg),
    twin_literal(Section, Slot),
    var_at(Section, Slot, Arg, Var).

% DEFINITION, local helper. twin_pair(Left, Right): some symmetry compares these
% two positions, so twin_same/2 grounds no other pair.
twin_pair(Left, Right) :- twin_cell(_, _, Left, Right, _, _).
twin_pair(Left, Right) :- twin_cell(_, _, _, _, Left, Right).

% DEFINITION, local helper. twin_same(Left, Right): two positions share a variable.
%   Left, Right  a compared pair, Left first.
% Used by the tie and the constraint below.
twin_same(Left, Right) :- twin_pair(Left, Right), twin_var(Left, Var), twin_var(Right, Var).

% DEFINITION, local helper. twin_same_mode(Source, Target): a literal may move
% between these two slots, which hold the same mode.
%   Source, Target  body slots of a compiled move.
% Used only by twin_invalid below.
twin_same_mode(Source, Target) :-
    twin_move(_, Source, Target),
    selected(body, Source, Mode),
    selected(body, Target, Mode),
    twin_compared_mode(Mode).

% DEFINITION, local helper. twin_orientable(Slot): this literal may swap operands.
%   Slot  a body slot holding an orientable mode.
% Used only by twin_invalid below.
twin_orientable(Slot) :- selected(body, Slot, Mode), twin_orientable_mode(Mode).

% DEFINITION, local helper. twin_invalid(Symmetry): the clause does not admit
% this symmetry, because it moves different modes or swaps a literal that fixes
% its operand order.
%   Symmetry  a compiled symmetry.
% Case 1: a move between different modes or empty slots.
twin_invalid(Symmetry) :- twin_move(Symmetry, Source, Target), not twin_same_mode(Source, Target).
% Same predicate. Case 2: a swap of a literal without interchangeable operands.
twin_invalid(Symmetry) :- twin_swap(Symmetry, Slot), not twin_orientable(Slot).

% DEFINITION, local helper. twin_tied(Symmetry, Cell): the clause and its twin
% agree on every position pair before Cell.
%   Symmetry  an admitted symmetry.
%   Cell      an index into its compiled cells.
% Used only by the constraint below.
twin_tied(Symmetry, 0) :- twin_symmetry(Symmetry), not twin_invalid(Symmetry).
% Same predicate. Both share the pair.
twin_tied(Symmetry, Cell+1) :-
    twin_tied(Symmetry, Cell),
    twin_cell(Symmetry, Cell, Left, Right, Source, Target),
    twin_same(Left, Right),
    twin_same(Source, Target).
% Same predicate. Neither shares the pair.
twin_tied(Symmetry, Cell+1) :-
    twin_tied(Symmetry, Cell),
    twin_cell(Symmetry, Cell, Left, Right, Source, Target),
    not twin_same(Left, Right),
    not twin_same(Source, Target).

% CONSTRAINT. At the first pair where they differ, the twin must not share the
% variable that the clause does not: that twin would be smaller.
%   Symmetry, Cell  an admitted symmetry and the first differing cell.
%   Left, Right     the pair read in this clause.
%   Source, Target  the pair the twin holds there.
% With the symmetry swapping slots 0 and 1:
%   pruned: :- p(V0,V1), p(V2,V0).     the swap shares V0 earlier
%   kept:   :- p(V0,V1), p(V1,V2).
:- twin_tied(Symmetry, Cell),
    twin_cell(Symmetry, Cell, Left, Right, Source, Target),
    twin_same(Source, Target),
    not twin_same(Left, Right).
