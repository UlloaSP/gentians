% Translate flattened placeholders into tuple, condition and result roles.
% The compiler supplies static role-to-position mappings.
% Condition identifies an occurrence; Predicate alone does not.
%
% Two families of views coexist. The first (tuple/condition/result) exists only
% for the single-element equality subset "#count{T : c1, ..., cn} = R" with
% positive atom conditions. The second (element_*, output, guard) exists for
% every body aggregate and keeps each element apart.


% DEFINITION, reusable. aggregate_tuple_binding(Slot, Position, Variable): a
% tuple term of the aggregate at body Slot.
%   Slot      body slot of an aggregate of the single-element subset.
%   Position  zero-based index inside the tuple: in "#sum{V0,V1 : ...}" V0 is
%             at 0 and V1 at 1.
%   Variable  variable id written there.
% Shared by symmetry/aggregates.lp (tuple order and the sum weight),
% pruning/policies/aggregates.lp (no repeated tuple variable) and
% pruning/redundancy/aggregates.lp (key-determined discriminators).
aggregate_tuple_binding(Slot, Position, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_tuple_arg(Mode, Position, FlatPosition),
    var_at(body, Slot, FlatPosition, Variable).

% DEFINITION, reusable. aggregate_tuple_var(Slot, Variable): Variable is some
% tuple term of the aggregate at body Slot.
%   Slot      body slot of an aggregate of the single-element subset.
%   Variable  variable id at any tuple position.
% Drops the position for consumers that only ask about membership:
% representation/variables.lp, legality/aggregates.lp, symmetry/aggregates.lp
% and pruning/redundancy/aggregates.lp.
aggregate_tuple_var(Slot, Variable) :- aggregate_tuple_binding(Slot, _, Variable).

% DEFINITION, reusable. aggregate_condition_position(Slot, Position, Variable):
% a condition placeholder of the aggregate at body Slot, by storage position.
%   Slot      body slot of an aggregate of the single-element subset.
%   Position  flattened placeholder position of the mode (not an argument
%             index); it is unique across all conditions of the aggregate.
%   Variable  variable id written there.
% Shared by aggregate_condition_var below and pruning/policies/aggregates.lp,
% which needs distinct positions to detect one variable written twice.
aggregate_condition_position(Slot, Position, Variable) :-
    selected(body, Slot, Mode),
    mode_aggregate_condition_arg(Mode, _, _, Position),
    var_at(body, Slot, Position, Variable).

% DEFINITION, reusable. aggregate_condition_var(Slot, Variable): Variable
% occurs in some condition of the aggregate at body Slot.
%   Slot      body slot of an aggregate of the single-element subset.
%   Variable  variable id at any condition placeholder.
% Shared by representation/variables.lp and legality/aggregates.lp.
aggregate_condition_var(Slot, Variable) :- aggregate_condition_position(Slot, _, Variable).

% DEFINITION, reusable. aggregate_condition_binding(Slot, Condition, Position,
% Variable): an argument of one condition occurrence.
%   Slot       body slot of an aggregate of the single-element subset.
%   Condition  zero-based index of the condition occurrence. Two conditions on
%              the same predicate have different indices.
%   Position   source argument index inside that condition's atom: in
%              "p(V4,V5)" V4 is at 0 and V5 at 1.
%   Variable   variable id written there.
% Shared by aggregate_condition_arg below and symmetry/aggregates.lp, which
% orders the arguments of one condition.
aggregate_condition_binding(Slot, Condition, Position, Variable) :-
    selected(body, Slot, Mode),
    mode_aggregate_condition_arg(Mode, Condition, Position, FlatPosition),
    var_at(body, Slot, FlatPosition, Variable).

% DEFINITION, reusable. aggregate_condition_arg(Slot, Condition, Predicate,
% Position, Variable): the same binding, tagged with the condition's predicate.
%   Slot       body slot of the aggregate.
%   Condition  index of the condition occurrence.
%   Predicate  signed predicate id of that condition's atom.
%   Position   source argument index of Predicate, so it lines up with the
%              argument positions named by property facts.
%   Variable   variable id written there.
% Shared by the property checks that also apply inside aggregates:
% pruning/properties/arg_equal.lp, arg_distinct.lp and symmetric.lp, and by
% pruning/redundancy/aggregates.lp (keys).
aggregate_condition_arg(Slot, Condition, Predicate, Position, Variable) :-
    selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Predicate, _),
    aggregate_condition_binding(Slot, Condition, Position, Variable).

% DEFINITION, reusable. aggregate_result_var(Slot, Variable): the value the
% aggregate at body Slot is equated to.
%   Slot      body slot of an aggregate of the single-element subset.
%   Variable  variable id of the result: V2 in "#count{V0 : p(V0)} = V2".
% Shared by representation/variables.lp, legality/aggregates.lp,
% legality/asp_safety.lp and legality/flow/seeds.lp (the result is a produced,
% safe output), pruning/policies/aggregates.lp and
% pruning/redundancy/aggregates.lp.
aggregate_result_var(Slot, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_result_arg(Mode, Position),
    var_at(body, Slot, Position, Variable).

% DEFINITION, reusable. aggregate_internal_arg(Slot, Position): a placeholder
% that lies inside the braces of the aggregate at body Slot.
%   Slot      body slot of an aggregate.
%   Position  flattened placeholder position of a tuple term or a condition;
%             never the result or a guard.
% Shared by aggregate_internal_position below, legality/scopes.lp (interior
% names can be local) and pruning/redundancy/aggregates.lp (the inputs that
% two aggregates must share to be the same computation).
% Case 1: tuple positions of the single-element subset.
aggregate_internal_arg(Slot, Position) :-
    selected(body, Slot, Mode), mode_aggregate_tuple_arg(Mode, _, Position).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: condition positions of the single-element subset.
aggregate_internal_arg(Slot, Position) :-
    selected(body, Slot, Mode),
    mode_aggregate_condition_arg(Mode, _, _, Position).

% DEFINITION, reusable. aggregate_internal_position(body, Slot, Position): the
% same fact with its section made explicit.
%   body      the section; aggregates handled here occur only in the body.
%   Slot      body slot of an aggregate.
%   Position  flattened interior placeholder position.
% Consumed by legality/scopes.lp, whose global_context_var rule ranges over
% both sections and therefore needs a Section argument to negate against.
aggregate_internal_position(body, Slot, Position) :- aggregate_internal_arg(Slot, Position).

% DEFINITION, local helper. aggregate_element_tuple_binding(Slot, Element,
% Position, Variable): a tuple term of one element of any body aggregate.
%   Slot      body slot of an aggregate.
%   Element   zero-based index of the element ("t1:c1 ; t2:c2" has 0 and 1).
%   Position  index inside that element's tuple; for a set aggregate, the
%             argument index of the element's conclusion atom.
%   Variable  variable id written there.
% Used only by aggregate_element_tuple_var below.
aggregate_element_tuple_binding(Slot, Element, Position, Variable) :-
    selected(body, Slot, Mode),
    mode_aggregate_element_tuple_arg(Mode, Element, Position, FlatPosition),
    var_at(body, Slot, FlatPosition, Variable).

% DEFINITION, reusable. aggregate_element_tuple_var(Slot, Element, Variable):
% Variable is a tuple term of that element.
%   Slot, Element  the aggregate element.
%   Variable       variable id at any of its tuple positions.
% Consumed by legality/aggregates.lp.
aggregate_element_tuple_var(Slot, Element, Variable) :-
    aggregate_element_tuple_binding(Slot, Element, _, Variable).

% DEFINITION, local helper. aggregate_element_condition_binding(Slot, Element,
% Condition, Argument, Variable): an argument of one condition of one element.
%   Slot, Element  the aggregate element.
%   Condition      zero-based index of the condition inside that element.
%   Argument       source argument index inside that condition.
%   Variable       variable id written there.
% Used only by aggregate_element_condition_var below.
aggregate_element_condition_binding(Slot, Element, Condition, Argument, Variable) :-
    selected(body, Slot, Mode),
    mode_aggregate_element_condition_arg(Mode, Element, Condition, Argument, FlatPosition),
    var_at(body, Slot, FlatPosition, Variable).

% DEFINITION, reusable. aggregate_element_condition_var(Slot, Element,
% Variable): Variable occurs in some condition of that element.
%   Slot, Element  the aggregate element.
%   Variable       variable id at any condition placeholder of the element,
%                  whatever the condition's polarity or kind.
% Consumed by legality/aggregates.lp.
aggregate_element_condition_var(Slot, Element, Variable) :-
    aggregate_element_condition_binding(Slot, Element, _, _, Variable).

% DEFINITION, reusable. aggregate_element_positive_condition_var(Slot,
% Element, Condition, Variable): a positive atom condition mentions Variable.
%   Slot, Element  the aggregate element.
%   Condition      index of a condition that is an atom without default
%                  negation.
%   Variable       variable id at a placeholder of that condition.
% Consumed by legality/scopes.lp: only such a condition can bind a local
% variable of the element.
aggregate_element_positive_condition_var(Slot, Element, Condition, Variable) :-
    selected(body, Slot, Mode),
    mode_aggregate_element_positive_arg(Mode, Element, Condition, Position),
    var_at(body, Slot, Position, Variable).

% DEFINITION, reusable. aggregate_element_arg(Slot, Element, Position): a
% placeholder that belongs to one element of the aggregate at body Slot.
%   Slot      body slot of an aggregate.
%   Element   index of the element that owns the placeholder.
%   Position  flattened placeholder position.
% Shared by the third aggregate_internal_arg rule below, legality/aggregates.lp
% (each local name is bound in its own element) and legality/typing.lp
% (different elements are different scopes).
% Case 1: tuple and conclusion positions of the element.
aggregate_element_arg(Slot, Element, Position) :-
    selected(body, Slot, Mode),
    mode_aggregate_element_tuple_arg(Mode, Element, _, Position).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: condition positions of the element.
aggregate_element_arg(Slot, Element, Position) :-
    selected(body, Slot, Mode),
    mode_aggregate_element_condition_arg(Mode, Element, _, _, Position).

% DEFINITION, reusable. aggregate_internal_arg(Slot, Position), case 3: every
% element placeholder is interior, which extends the view from the
% single-element subset to all body aggregates.
aggregate_internal_arg(Slot, Position) :- aggregate_element_arg(Slot, _, Position).

% DEFINITION, reusable. aggregate_output_var(Slot, Variable): a variable the
% aggregate at body Slot assigns through an equality guard.
%   Slot      body slot of an aggregate.
%   Variable  variable id at an output guard: V1 in "#sum{...} = V1".
% Shared by legality/asp_safety.lp and legality/flow/seeds.lp (an output is
% safe and produced) and pruning/policies/aggregates.lp (it must be used).
aggregate_output_var(Slot, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_output_arg(Mode, Position),
    var_at(body, Slot, Position, Variable).

% DEFINITION, reusable. aggregate_guard_var(Slot, Variable): a variable the
% aggregate at body Slot only compares against.
%   Slot      body slot of an aggregate.
%   Variable  variable id at a non-producing guard: V1 in "#count{...} > V1"
%             or either bound of "V1 <= #count{...} <= V2".
% Consumed by legality/aggregates.lp, which requires it to be safe elsewhere.
aggregate_guard_var(Slot, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_guard_arg(Mode, Position),
    var_at(body, Slot, Position, Variable).
