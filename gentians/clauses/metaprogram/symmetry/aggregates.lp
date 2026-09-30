% Order count tuples and eligible full-local condition permutations.
% The one-condition template must cover exactly the tuple; sum permutations
% keep the weight fixed. Global variables cannot be exchanged.


% CONSTRAINT. The tuple of a #count aggregate must list its variables in
% ascending id order: a count does not depend on the order of its tuple terms.
%   Slot           body slot of a #count of the single-element subset.
%   First, Second  two tuple positions, First before Second, that the template
%                  lets swap: equal type, direction and label
%                  (interchangeable_tuple_args).
%   Left, Right    the variable ids written at them.
%   pruned: #count{V1,V0 : p(V0,V1)} = V2
%   kept:   #count{V0,V1 : p(V0,V1)} = V2
% Swapping two tuple terms moves each variable to the other position. With
% #count{var(node),var(colour) : assigned(var(colour),var(node))} that would
% give a node variable the colour type, so such a tuple keeps its order.
:- selected(body, Slot, Mode), count_aggregate_mode(Mode),
    interchangeable_tuple_args(Mode, First, Second),
    aggregate_tuple_binding(Slot, First, Left),
    aggregate_tuple_binding(Slot, Second, Right), First < Second, Left > Right.

% DEFINITION, local helper. full_local_condition(Slot, Mode): the aggregate
% has one condition whose arguments are exactly its tuple, all of them local.
%   Slot  body slot of the aggregate.
%   Mode  its mode: one condition (index 0) whose arity equals the tuple
%         width, no condition variable outside the tuple, and no tuple
%         variable that is clause-global.
% Example: "#count{V0,V1 : p(V0,V1)}" when V0 and V1 occur nowhere else. Only
% then is renaming the local variables a pure symmetry. Used by the two
% orderable views below.
full_local_condition(Slot, Mode) :-
    selected(body, Slot, Mode), aggregate_shape(Mode, Arity, 1),
    aggregate_condition_atom(Mode, 0, _, Arity),
    not condition_has_non_tuple_variable(Slot),
    not aggregate_tuple_has_global_variable(Slot).

% DEFINITION, local helper. condition_has_non_tuple_variable(Slot): condition
% 0 of the aggregate mentions a variable that is not a tuple term.
%   Slot  body slot of the aggregate, as V1 in "#count{V0 : p(V0,V1)}".
% Used only, negated, by full_local_condition.
condition_has_non_tuple_variable(Slot) :-
    aggregate_condition_binding(Slot, 0, _, Variable),
    not aggregate_tuple_var(Slot, Variable).

% DEFINITION, local helper. aggregate_tuple_has_global_variable(Slot): some
% tuple term of the aggregate is a clause-global variable.
%   Slot  body slot of the aggregate.
% A global variable is tied to the rest of the clause and cannot be renamed
% freely. Used only, negated, by full_local_condition.
aggregate_tuple_has_global_variable(Slot) :-
    aggregate_tuple_var(Slot, Variable), global_context_var(Variable).

% DEFINITION, local helper. count_condition_orderable(Slot): the arguments of
% the condition of this #count may be put in canonical order.
%   Slot  body slot of a #count whose condition is full-local.
% Used only by the second constraint below.
count_condition_orderable(Slot) :-
    full_local_condition(Slot, Mode), count_aggregate_mode(Mode).

% DEFINITION, local helper. sum_condition_orderable(Slot, Weight): the
% arguments of the condition of this #sum may be ordered, except the weight.
%   Slot    body slot of a #sum whose condition is full-local.
%   Weight  variable id at tuple position 0, the summed term. It must keep its
%           place: exchanging it with another variable changes the sum.
% Used only by the third constraint below.
sum_condition_orderable(Slot, Weight) :-
    full_local_condition(Slot, Mode), sum_aggregate_mode(Mode),
    aggregate_tuple_binding(Slot, 0, Weight).

% CONSTRAINT. In an orderable #count, the condition lists its variables in
% ascending id order.
%   Slot           body slot of the aggregate.
%   Mode           its template.
%   First, Second  two argument positions of condition 0, First before Second,
%                  that the template lets swap
%                  (interchangeable_condition_args).
%   Left, Right    the variable ids written at them.
% Together with the tuple constraint above, only one naming survives:
%   pruned: #count{V0,V1 : p(V1,V0)} = V2
%   kept:   #count{V0,V1 : p(V0,V1)} = V2
% The kept form writes the condition arguments in the other order, so it
% exists only when the template admits that. With
% #count{var(node),var(colour) : assigned(var(colour),var(node))} it does
% not, and the descending form is the only one:
%   kept:   #count{V1,V2 : assigned(V2,V1)} = V0
:- count_condition_orderable(Slot),
    selected(body, Slot, Mode),
    interchangeable_condition_args(Mode, 0, First, Second),
    aggregate_condition_binding(Slot, 0, First, Left),
    aggregate_condition_binding(Slot, 0, Second, Right), First < Second, Left > Right.

% CONSTRAINT. In an orderable #sum, the condition lists its non-weight
% variables in ascending id order.
%   Slot           body slot of the aggregate.
%   Weight         the summed variable, skipped by the comparison.
%   Mode           its template.
%   First, Second  two argument positions of condition 0, First before Second,
%                  that the template lets swap.
%   Left, Right    the variable ids written at them, neither being Weight.
%   pruned: #sum{V0,V1,V2 : p(V0,V2,V1)} = V3    V2 before V1 among non-weights
%   kept:   #sum{V0,V1,V2 : p(V0,V1,V2)} = V3
%   kept:   #sum{V1,V0,V2 : p(V0,V1,V2)} = V3    the weight V1 is exempt
:- sum_condition_orderable(Slot, Weight),
    selected(body, Slot, Mode),
    interchangeable_condition_args(Mode, 0, First, Second),
    aggregate_condition_binding(Slot, 0, First, Left),
    aggregate_condition_binding(Slot, 0, Second, Right), First < Second,
    Left != Weight, Right != Weight, Left > Right.
