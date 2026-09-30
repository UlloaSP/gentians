% Remove key-determined tuple discriminators only if a shorter template exists.
% Reject repeated aggregate computations with different result ids. The key
% check uses the existing predicate-level projection of condition arguments.


% DEFINITION, local helper. aggregate_key_input_missing(Slot, Condition, Key):
% the tuple of the aggregate does not contain every key argument of that
% condition.
%   Slot       body slot of an aggregate of the single-element subset.
%   Condition  index of one of its conditions.
%   Key        id of a key (a set of argument positions, key_arg/2).
% It holds when some argument position of Key holds, in that condition, a
% variable that is not a tuple term. The rule does not check that Key belongs
% to the condition's predicate; the constraint at the end supplies that join
% through key_pred/2. Used only, negated, by that constraint.
aggregate_key_input_missing(Slot, Condition, Key) :-
    key_arg(Key, Input),
    aggregate_condition_arg(Slot, Condition, _, Input, InputVar),
    not aggregate_tuple_var(Slot, InputVar).

% DEFINITION, local helper. aggregate_input_differs(Slot0, Slot1): two
% adjacent aggregates of the same mode differ in some interior variable.
%   Slot0  body slot of an aggregate of the single-element subset.
%   Slot1  the next slot (Slot0 + 1), holding the same mode.
% "Interior" is every tuple and condition placeholder, not the result. Used
% only, negated, by same_aggregate_inputs below.
aggregate_input_differs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    aggregate_shape(Mode, _, _),
    Slot1 = Slot0 + 1,
    aggregate_internal_arg(Slot0, Arg),
    var_at(body, Slot0, Arg, Left),
    var_at(body, Slot1, Arg, Right),
    Left != Right.

% DEFINITION, local helper. same_aggregate_inputs(Slot0, Slot1): two adjacent
% aggregates of the same mode have identical interiors, so they compute the
% same value.
%   Slot0, Slot1  adjacent body slots, as above.
% Adjacency suffices because equal modes are contiguous and sorted
% (symmetry/slots.lp). Used only by the constraint below.
same_aggregate_inputs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    aggregate_shape(Mode, _, _),
    Slot1 = Slot0 + 1,
    not aggregate_input_differs(Slot0, Slot1).

% CONSTRAINT. The same aggregate computed twice may not be given two result
% variables: both results are necessarily equal, so the clause is the one
% that computes it once and reuses the result.
%   Slot0, Slot1      adjacent aggregates with identical interiors.
%   Result0, Result1  their result variable ids, which differ.
%   pruned: h(V1,V2) :- #count{V0 : p(V0)} = V1, #count{V0 : p(V0)} = V2.
%   kept:   h(V1,V1) :- #count{V0 : p(V0)} = V1.
:- same_aggregate_inputs(Slot0, Slot1),
    aggregate_result_var(Slot0, Result0),
    aggregate_result_var(Slot1, Result1),
    Result0 != Result1.

% CONSTRAINT. A tuple term that the rest of the tuple already determines
% through a key adds nothing, so the aggregate is generated only in its
% shorter form, provided the language bias declares that shorter form.
%   Slot            body slot of an aggregate whose mode has a declared
%                   variant with one tuple term fewer.
%   Position        a tuple position other than 0 (position 0 may be a weight).
%   OutputVariable  the variable id written there.
%   Condition, Predicate, Output
%                   a condition on Predicate that holds OutputVariable at its
%                   argument Output.
%   Key             a key of Predicate that does not contain Output and whose
%                   arguments are all tuple terms.
% With key_pred(p,k), key_arg(k,0) (argument 0 of p is a key) and both
% "#count{var : p(..)}" and "#count{var,var : p(..)}" declared:
%   pruned: #count{V0,V1 : p(V0,V1)} = V2     V0 determines V1
%   kept:   #count{V0 : p(V0,V1)} = V2        the shorter form
% Without the shorter declaration the first form is kept.
:- selected(body, Slot, Mode), aggregate_has_shorter_mode(Mode),
    aggregate_tuple_binding(Slot, Position, OutputVariable), Position > 0,
    aggregate_condition_arg(Slot, Condition, Predicate, Output, OutputVariable),
    key_pred(Predicate, Key), not key_arg(Key, Output),
    not aggregate_key_input_missing(Slot, Condition, Key).
