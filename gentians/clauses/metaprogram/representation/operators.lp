% Operator classifications and normalized relations over selected variables.
% mode_kind classifies operators; comparison_operator records simple operators.
% selected_lt/selected_leq orient >/>= in reverse; neq and distinctness are symmetric.
% These predicates describe selected comparisons, not their transitive closure.

% DEFINITION, reusable. arithmetic_mode(Mode): Mode is an arithmetic literal
% such as "X+Y=Z".
%   Mode  id of a template of kind arithmetic.
% Shared by legality/asp_safety.lp, legality/flow/closure.lp and
% requirements.lp (an arithmetic literal needs bound operands) and
% pruning/redundancy/arithmetic.lp (repeated computations).
arithmetic_mode(Mode) :- mode_kind(Mode, arithmetic).

% DEFINITION, reusable. comparison_mode(Mode): Mode is a comparison literal,
% simple or chained.
%   Mode  id of a template of kind comparison.
% Shared by legality/asp_safety.lp and legality/flow/requirements.lp, which
% require compared variables to be bound elsewhere.
comparison_mode(Mode) :- mode_kind(Mode, comparison).

% DEFINITION, reusable. selected_lt(Left, Right): the body contains the
% explicit strict comparison "Left < Right" between two variables.
%   Left   variable id on the smaller side.
%   Right  variable id on the greater side.
% Only simple binary comparisons have comparison_operator/2; their operands
% are placeholders 0 and 1. Shared so that consumers reason about one
% orientation instead of four operators: inference/numeric.lp,
% pruning/contradictions/comparisons.lp and numeric.lp,
% pruning/redundancy/comparisons.lp and numeric.lp.
% Case 1: a "<" literal, read as written.
selected_lt(Left, Right) :-
    selected(body, Slot, Mode),
    comparison_operator(Mode, lt),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

% DEFINITION, reusable. Same predicate.
% Case 2: a ">" literal, read in reverse. "V3 > V1" yields selected_lt(1,3):
% the head swaps the operands, so the first argument is still the smaller one.
selected_lt(Right, Left) :-
    selected(body, Slot, Mode),
    comparison_operator(Mode, gt),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

% DEFINITION, reusable. selected_leq(Left, Right): the body contains the
% explicit non-strict comparison "Left <= Right".
%   Left   variable id on the smaller-or-equal side.
%   Right  variable id on the greater-or-equal side.
% Shared for the same reason and by the same modules as selected_lt/2, plus
% pruning/policies/comparisons.lp.
% Case 1: a "<=" literal, read as written.
selected_leq(Left, Right) :-
    selected(body, Slot, Mode),
    comparison_operator(Mode, leq),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

% DEFINITION, reusable. Same predicate.
% Case 2: a ">=" literal, read in reverse. "V3 >= V1" yields selected_leq(1,3).
selected_leq(Right, Left) :-
    selected(body, Slot, Mode),
    comparison_operator(Mode, geq),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

% DEFINITION, reusable. selected_neq(Left, Right): the body contains the
% explicit disequality "Left != Right".
%   Left, Right  the two variable ids, in the written order for this rule.
% Shared by known_unequal_values below and pruning/redundancy/comparisons.lp.
selected_neq(Left, Right) :-
    selected(body, Slot, Mode),
    comparison_operator(Mode, neq),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

% DEFINITION, reusable. Same predicate, symmetric closure: "V0 != V1" also
% yields selected_neq(1,0), so consumers need not test both orders.
selected_neq(Right, Left) :- selected_neq(Left, Right).

% DEFINITION, reusable. known_unequal_values(Left, Right): the clause itself
% proves that the two variables take different ground values.
%   Left, Right  variable ids.
% Different ids alone prove nothing: V0 and V1 may be equal at run time. This
% predicate is the stronger premise that pruning/properties/functional.lp,
% functional_set.lp and cardinality_upper.lp require before pruning.
% Case 1: an explicit disequality.
known_unequal_values(Left, Right) :- selected_neq(Left, Right).

% DEFINITION, reusable. Same predicate.
% Case 2: an explicit strict comparison, since Left < Right entails Left != Right.
known_unequal_values(Left, Right) :- selected_lt(Left, Right).

% DEFINITION, reusable. Same predicate, symmetric closure.
known_unequal_values(Right, Left) :- known_unequal_values(Left, Right).
