% Track grounding safety independently from mode-directed readiness.
% Positive normal body atoms bind their variables. Arithmetic results become
% safe after their operands; aggregate results are safe outputs. Relation
% outputs proved safe by Clingo are handled in legality/flow/closure.lp.

% DEFINITION, reusable. asp_safe(Var): Clingo can ground Var; some literal of
% the body supplies its values.
%   Var  clause-global variable id.
% Shared by the safety constraints below, legality/aggregates.lp (guards),
% legality/scopes.lp (global variables of conditionals and inputs of local
% comparisons) and legality/flow/closure.lp, which adds one more case.
% Case 1: the result of a single-element equality aggregate, V1 in
% "#count{V0 : p(V0)} = V1".
asp_safe(Var) :- aggregate_result_var(_, Var).
% DEFINITION, reusable. Same predicate. Case 2: the equality output of any
% body aggregate.
asp_safe(Var) :- aggregate_output_var(_, Var).

% DEFINITION, reusable. normal_positive_body_var(Var): a positive plain body
% atom grounds Var.
%   Var  variable id written in a positive plain body atom at a placeholder
%        that every binding alternative of that atom grounds (see
%        pooled_body_missing_var in representation/arguments.lp).
% Stricter than asp_safe: results of arithmetic, aggregates and relations do
% not count. Shared by legality/aggregates.lp (aggregate interiors need this
% independent support), pruning/policies/singletons.lp (existential
% projections) and pruning/redundancy/arithmetic.lp.
normal_positive_body_var(Var) :-
    positive_body_literal(Slot, Mode, _, _),
    var_at(body, Slot, _, Var),
    not pooled_body_missing_var(Slot, Var).

% DEFINITION, reusable. asp_safe(Var), case 3: a positive plain body atom
% grounds Var.
asp_safe(Var) :- normal_positive_body_var(Var).

% DEFINITION, local helper. head_var(Var): Var occurs in the head as a
% clause-global variable.
%   Var  variable id at a head placeholder that is neither local to a
%        conditional head element nor local to a choice/aggregate head element.
% In "p(V0) : q(V0,V1)" with V0 and V1 occurring nowhere else, neither is a
% head_var. Used only by the head safety constraint below.
head_var(Var) :-
    var_at(head, Slot, Arg, Var),
    not conditional_local_at(head, Slot, Arg),
    not head_aggregate_local_at(head, Slot, Arg).

% DEFINITION, local helper. negated_var(Var): Var occurs in a default-negated
% plain body atom.
%   Var  variable id written in "not p(...)" or "not not p(...)".
% Used only by the negation safety constraint below.
negated_var(Var) :-
    negative_body_literal(Slot, Mode, _, _),
    var_at(body, Slot, _, Var).

% DEFINITION, local helper. comparison_var(Var): Var is read, not assigned,
% by a body comparison.
%   Var  variable id at a comparison placeholder whose declared direction is
%        not output. In "V0 < V1" both; in an assigning "V2 = V0 + 1" declared
%        with V2 as output, only V0.
% Used only by the comparison safety constraint below.
comparison_var(Var) :-
    selected(body, Slot, Mode),
    comparison_mode(Mode),
    var_at(body, Slot, Arg, Var),
    not mode_arg_direction(Mode, Arg, output).

% DEFINITION, local helper. arithmetic_operand_var(Var): Var is an operand of
% a body arithmetic literal.
%   Var  variable id on the left or right of "Left op Right = Result".
% Used only by the operand safety constraint below.
arithmetic_operand_var(Var) :-
    selected(body, Slot, Mode),
    arithmetic_mode(Mode),
    arithmetic_operand(Slot, _, Var).

% DEFINITION, local helper. arithmetic_result_safe(Slot): the arithmetic
% literal at body Slot can compute its result.
%   Slot  body slot of "Left op Right = Result" whose two operands are
%         already asp_safe.
% Used only by the next rule. The dependency is positive and recursive, so a
% chain "V0+V1=V2, V2+V2=V3" becomes safe step by step.
arithmetic_result_safe(Slot) :-
    selected(body, Slot, Mode),
    arithmetic_mode(Mode),
    arithmetic_operand(Slot, left, Left),
    arithmetic_operand(Slot, right, Right),
    asp_safe(Left),
    asp_safe(Right).

% DEFINITION, reusable. asp_safe(Var), case 4: the result of an arithmetic
% literal whose operands are safe.
%   Slot  body slot of that literal.
%   Var   variable id of its result.
asp_safe(Var) :-
    arithmetic_result_safe(Slot),
    arithmetic_result(Slot, Var).

% CONSTRAINT. Every clause-global head variable must be ASP-safe.
%   Var  variable id of a global head occurrence.
%   pruned: h(V0,V1) :- p(V0).          nothing grounds V1
%   pruned: h(V0) :- not p(V0).         negation grounds nothing
%   kept:   h(V0,V1) :- p(V0), q(V1).
:- head_var(Var), not asp_safe(Var).

% A positive atom need not ground every variable it mentions: a pool
% alternative may omit it, and non-invertible arithmetic such as q(X+X) or
% q(|X|) grounds nothing. Such a variable must be safe elsewhere.
% CONSTRAINT. A variable that a partially binding body atom mentions without
% grounding must be ASP-safe through another literal.
%   Slot  body slot of the partially binding atom.
%   Var   variable id it leaves ungrounded.
%   pruned: :- q(V0+V1).                 neither operand is grounded
%   kept:   :- q(V0+V1), r(V0), r(V1).
:- selected(body, Slot, _),
    var_at(body, Slot, _, Var),
    pooled_body_missing_var(Slot, Var),
    not asp_safe(Var).

% CONSTRAINT. Every variable of a default-negated body atom must be ASP-safe.
%   Var  variable id written under negation.
%   pruned: :- p(V0), not q(V0,V1).      V1 occurs only under negation
%   kept:   :- p(V0), r(V1), not q(V0,V1).
:- negated_var(Var), not asp_safe(Var).

% CONSTRAINT. Every variable a comparison reads must be ASP-safe.
%   Var  variable id at a non-output comparison placeholder.
%   pruned: :- p(V0), V0 < V1.           V1 is only compared
%   kept:   :- p(V0), p(V1), V0 < V1.
:- comparison_var(Var), not asp_safe(Var).

% CONSTRAINT. Every operand of an arithmetic literal must be ASP-safe.
%   Var  variable id of an operand.
%   pruned: h(V2) :- p(V0), V0+V1=V2.    V1 is never grounded
%   kept:   h(V2) :- p(V0), p(V1), V0+V1=V2.
:- arithmetic_operand_var(Var), not asp_safe(Var).
