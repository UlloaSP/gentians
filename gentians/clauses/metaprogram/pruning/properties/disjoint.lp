% Closed-world disjoint argument property.
%
% Python emits disjoint_arg/4 for argument pairs that never share values in the
% observed closed world. This file rejects joins over such positions.


% CONSTRAINT. Two positive body atoms may not join on argument positions
% whose value sets are disjoint: no value satisfies both, so the body could
% never hold.
%   Slot0 < Slot1  body slots; the atom of Pred0 occupies the earlier one.
%   Pred0, Arg0    first predicate and one of its argument positions.
%   Pred1, Arg1    second predicate and one of its argument positions.
%   Var            the variable id written at both positions.
% With disjoint_arg(person,0,city,0) (no person is a city):
%   pruned: :- person(V0), city(V0).
%   kept:   :- person(V0), city(V1), lives(V0,V1).
:- positive_body_literal(Slot0, _, Pred0, _),
    positive_body_literal(Slot1, _, Pred1, _),
    Slot0 < Slot1,
    disjoint_arg(Pred0, Arg0, Pred1, Arg1),
    var_at(body, Slot0, Arg0, Var),
    var_at(body, Slot1, Arg1, Var).

% DEFINITION, local helper. tuple_mutex_pair(Slot0, Slot1, Projection):
% the positive atoms at two different slots have a tuple-mutex mapping.
%   Slot0       body slot of the left signed predicate.
%   Slot1       body slot of the right signed predicate, with the same arity.
%   Projection  complete argument mapping attached to this predicate pair.
% Mapping ids may be shared by several predicate pairs. This view retains
% actual predicate membership before projecting it away: a mapping for p/q
% and r/s does not relate p/s. Each slot holds one selected mode, hence one
% predicate. Factoring this test avoids repeating the predicate-pair join
% for every argument and variable binding. Used only by the mismatch helper
% and constraint below; it adds no choices or exclusions by itself.
tuple_mutex_pair(Slot0, Slot1, Projection) :-
    positive_body_literal(Slot0, _, Pred0, Arity),
    positive_body_literal(Slot1, _, Pred1, Arity),
    Slot0 != Slot1,
    tuple_mutex_pred(Pred0, Pred1, Projection).

% DEFINITION, local helper. tuple_mutex_vars_differ(Slot0, Slot1, Projection):
% two body atoms are not aligned the way a tuple-mutex mapping requires.
%   Slot0       body slot of the atom playing the left predicate.
%   Slot1       body slot of the atom playing the right predicate.
%   Projection  id of a tuple-mutex mapping. Each tuple_mutex_arg(Projection,
%               TargetArg, SourceArg) pairs argument SourceArg of the left
%               atom with argument TargetArg of the right atom.
% It holds when some paired positions carry different variable ids. It is
% derived only for the pairs the constraint below inspects: two positive
% atoms whose predicates the mapping relates. Used only, negated, by that
% constraint.
tuple_mutex_vars_differ(Slot0, Slot1, Projection) :-
    tuple_mutex_pair(Slot0, Slot1, Projection),
    tuple_mutex_arg(Projection, TargetArg, SourceArg),
    var_at(body, Slot0, SourceArg, Var),
    arg(body, Slot1, TargetArg),
    not var_at(body, Slot1, TargetArg, Var).

% CONSTRAINT. Two positive body atoms may not be aligned by a mapping under
% which their predicates exclude each other: the body could never hold.
%   Slot0, Slot1  two different body slots, in either order.
%   Projection    the mapping; every pair of mapped positions holds the same
%                 variable id.
% With lt/2 proved exclusive with its own reverse (tuple_mutex_pred(lt,lt,m),
% tuple_mutex_arg(m,0,1), tuple_mutex_arg(m,1,0)):
%   pruned: :- lt(V0,V1), lt(V1,V0).
%   kept:   :- lt(V0,V1), lt(V1,V2).
:- tuple_mutex_pair(Slot0, Slot1, Projection),
    not tuple_mutex_vars_differ(Slot0, Slot1, Projection).
