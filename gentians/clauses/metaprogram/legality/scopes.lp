% Occurrences outside local constructs make a variable name clause-global.
% Separate aggregate/conditional interiors may reuse a name without binding one
% another. A local variable must be bound within its own element or conditional.
% Comparisons bind only when Clingo proves their output positions safe.
%
% A local region is identified by four values used throughout this file:
%   Section, Slot  the selected literal that contains the region.
%   Scope          conditional, aggregate (body) or head_aggregate.
%   Element        -1 for a conditional, the element index for a body
%                  aggregate, 0 for a choice/aggregate head element.

% DEFINITION, reusable. local_condition_bound(Section, Slot, Scope, Element,
% Var): inside that local region, Var receives its values from the region
% itself.
%   Section, Slot, Scope, Element  the local region (see the file header).
%   Var                            variable id bound there.
% Shared by the constraints of this file (conditionals and head elements) and
% by legality/aggregates.lp (body aggregate elements).
% Case 1: a positive atom condition of a conditional literal grounds Var in
% every binding alternative: q binds V0 in "p(V0) : q(V0)".
%   Condition  index of that condition.
local_condition_bound(Section, Slot, conditional, -1, Var) :-
    conditional_positive_condition_var(Section, Slot, Condition, Var),
    selected(Section, Slot, Mode),
    not local_pool_missing_var(Section, Slot, Mode, conditional, -1, Condition, Var).

% DEFINITION, reusable. Same predicate. Case 2: a positive atom condition of
% one element of a body aggregate: p binds V0 in "#count{V0 : p(V0)}".
local_condition_bound(body, Slot, aggregate, Element, Var) :-
    aggregate_element_positive_condition_var(Slot, Element, Condition, Var),
    selected(body, Slot, Mode),
    not local_pool_missing_var(body, Slot, Mode, aggregate, Element, Condition, Var).

% DEFINITION, reusable. Same predicate. Case 3: a positive atom condition of
% a choice or aggregate head element: node binds V0 in "{sel(V0) : node(V0)}".
local_condition_bound(head, Slot, head_aggregate, 0, Var) :-
    head_aggregate_positive_condition_var(Slot, Condition, Var),
    selected(head, Slot, Mode),
    not local_pool_missing_var(head, Slot, Mode, head_aggregate, 0, Condition, Var).

% DEFINITION, local helper. local_pool_alternative_var(Section, Slot, Scope,
% Element, Condition, Alternative, Var): one binding alternative of a local
% condition grounds Var.
%   Section, Slot, Scope, Element  the local region.
%   Condition    index of a positive atom condition that binds only
%                partially (a pool, or non-invertible arithmetic).
%   Alternative  index of one binding alternative of that condition.
%   Var          variable id at a placeholder this alternative grounds.
% Used only by local_pool_missing_var below.
local_pool_alternative_var(Section, Slot, Scope, Element, Condition, Alternative, Var) :-
    selected(Section, Slot, Mode),
    local_pool_alternative_arg(Mode, Scope, Element, Condition, Alternative, Position),
    var_at(Section, Slot, Position, Var).

% DEFINITION, local helper. local_pool_missing_var(Section, Slot, Mode, Scope,
% Element, Condition, Var): the local condition mentions Var but does not
% ground it.
%   Section, Slot, Scope, Element  the local region.
%   Mode       id of the mode selected at that slot.
%   Condition  index of the partially binding positive condition.
%   Var        variable id of that condition that some alternative omits.
% The local counterpart of pooled_body_missing_var. Used only, negated, by the
% three local_condition_bound rules above.
local_pool_missing_var(Section, Slot, Mode, Scope, Element, Condition, Var) :-
    selected(Section, Slot, Mode),
    local_pool_condition_arg(Mode, Scope, Element, Condition, Position),
    var_at(Section, Slot, Position, Var),
    local_pool_alternative(Mode, Scope, Element, Condition, Alternative),
    not local_pool_alternative_var(Section, Slot, Scope, Element, Condition, Alternative, Var).

% DEFINITION, local helper. local_comparison_input_ready(Section, Slot, Scope,
% Element, Condition, Variant, Position): one input of a local comparison is
% available.
%   Section, Slot, Scope, Element  the local region.
%   Condition  index of a comparison condition inside it.
%   Variant    one way, proved by Clingo, of reading that comparison as
%              "these positions in, those positions out".
%   Position   flattened placeholder position that the variant needs as input.
% Used only by the fourth local_condition_bound rule below.
% Case 1: the variable at that input is already bound in the same region.
local_comparison_input_ready(Section, Slot, Scope, Element, Condition, Variant, Position) :-
    selected(Section, Slot, Mode),
    local_comparison_input(Mode, Scope, Element, Condition, Variant, Position),
    var_at(Section, Slot, Position, Var),
    local_condition_bound(Section, Slot, Scope, Element, Var).

% DEFINITION, local helper. Same predicate. Case 2: the variable at that
% input is clause-global and ASP-safe.
local_comparison_input_ready(Section, Slot, Scope, Element, Condition, Variant, Position) :-
    selected(Section, Slot, Mode),
    local_comparison_input(Mode, Scope, Element, Condition, Variant, Position),
    var_at(Section, Slot, Position, Var),
    global_context_var(Var), asp_safe(Var).

% DEFINITION, reusable. local_condition_bound, case 4: a comparison condition
% assigns Var once every input of one of its variants is ready.
%   Condition, Variant  the comparison and the reading that is used.
%   Required            number of input positions of that variant.
%   Position            an output position of that variant.
%   Var                 variable id written there, now bound in the region.
% Example: in "p(V0) : q(V1), V0 = V1 + 1" the comparison binds V0 from V1.
local_condition_bound(Section, Slot, Scope, Element, Var) :-
    selected(Section, Slot, Mode),
    local_comparison_variant(Mode, Scope, Element, Condition, Variant, Required),
    Required <= #count { Input :
        local_comparison_input_ready(Section, Slot, Scope, Element, Condition, Variant, Input)
    },
    local_comparison_output(Mode, Scope, Element, Condition, Variant, Position),
    var_at(Section, Slot, Position, Var).

% DEFINITION, reusable. local_var_at(Section, Slot, Arg): the placeholder
% holds a local variable, invisible outside its construct.
%   Section, Slot  the selected literal.
%   Arg            placeholder position inside it.
% Shared by legality/linkedness.lp (local names link nothing) and
% legality/typing.lp (local scopes are typed separately).
% Case 1: a placeholder inside a body aggregate whose variable is not
% clause-global.
local_var_at(body, Slot, Arg) :-
    aggregate_internal_arg(Slot, Arg),
    var_at(body, Slot, Arg, Var),
    not global_context_var(Var).

% DEFINITION, reusable. global_context_var(Var): Var is clause-global.
%   Var  variable id with at least one occurrence outside every local
%        construct.
% Every occurrence of a global name denotes the same variable, including its
% occurrences inside aggregates and conditionals. Shared by this file,
% legality/aggregates.lp (global names need independent support) and
% symmetry/aggregates.lp (global names cannot be permuted).
% Case 1: an occurrence in a non-conditional literal, outside aggregate
% interiors and outside choice/aggregate head elements. Occurrences in a
% conditional literal, even in its conclusion, never make a name global.
global_context_var(Var) :-
    selected(Section, Slot, Mode),
    not conditional_mode(Mode),
    var_at(Section, Slot, Arg, Var),
    not aggregate_internal_position(Section, Slot, Arg),
    not head_aggregate_element_position(Section, Slot, Arg).

% DEFINITION, reusable. Same predicate. Case 2: a guard or cardinality bound
% of a head, as V0 in "V0 {sel(V1) : node(V1)} V0".
global_context_var(Var) :-
    selected(head, Slot, Mode), head_guard_arg(Mode, Arg),
    var_at(head, Slot, Arg, Var).

% DEFINITION, local helper. head_aggregate_element_position(head, Slot, Arg):
% the placeholder lies inside a choice/aggregate head element.
%   head  the section; such elements occur only in the head.
%   Slot  head slot of the element.
%   Arg   placeholder position of its tuple, its atom or one of its
%         conditions; never a guard.
% Used by global_context_var above and head_aggregate_local_at below.
head_aggregate_element_position(head, Slot, Arg) :-
    selected(head, Slot, Mode), head_aggregate_element_arg(Mode, Arg).

% DEFINITION, reusable. head_aggregate_local_at(head, Slot, Arg): the
% placeholder inside a head element holds a local variable.
%   head, Slot  the head element.
%   Arg         placeholder position whose variable is not clause-global.
% Shared by the constraint below, local_var_at below and
% legality/asp_safety.lp (such a placeholder is not a global head variable).
head_aggregate_local_at(head, Slot, Arg) :-
    head_aggregate_element_position(head, Slot, Arg),
    var_at(head, Slot, Arg, Var), not global_context_var(Var).

% DEFINITION, reusable. local_var_at, case 2: local placeholders of
% choice/aggregate head elements.
local_var_at(head, Slot, Arg) :- head_aggregate_local_at(head, Slot, Arg).

% DEFINITION, local helper. head_aggregate_positive_condition_var(Slot,
% Condition, Var): a positive atom condition of a head element mentions Var.
%   Slot       head slot of the element.
%   Condition  index of a condition that is an atom without default negation.
%   Var        variable id at a placeholder of that condition.
% Used only by the third local_condition_bound rule above.
head_aggregate_positive_condition_var(Slot, Condition, Var) :-
    selected(head, Slot, Mode),
    head_aggregate_positive_condition_arg(Mode, Condition, Arg),
    var_at(head, Slot, Arg, Var).

% CONSTRAINT. Every local variable of a choice/aggregate head element must be
% bound inside that element.
%   Slot, Arg  a local placeholder of the head element.
%   Var        variable id written there.
%   pruned: {sel(V0) : not blocked(V0)}.     negation binds nothing
%   kept:   {sel(V0) : node(V0)}.
:- head_aggregate_local_at(head, Slot, Arg),
    var_at(head, Slot, Arg, Var),
    not local_condition_bound(head, Slot, head_aggregate, 0, Var).

% DEFINITION, reusable. conditional_local_var(Section, Slot, Var): Var is
% local to the conditional literal at that slot.
%   Section, Slot  the selected conditional literal.
%   Var            variable id of it that is not clause-global.
% Shared by this file and pruning/policies/singletons.lp, which exempts local
% names.
conditional_local_var(Section, Slot, Var) :-
    conditional_var(Section, Slot, Var),
    not global_context_var(Var).

% DEFINITION, reusable. conditional_local_at(Section, Slot, Arg): the
% placeholder of a conditional literal holds a local variable.
%   Section, Slot  the selected conditional literal.
%   Arg            placeholder position of it holding a local variable,
%                  excluding head guard positions.
% Shared by local_var_at below and legality/asp_safety.lp (such a placeholder
% is not a global head variable).
conditional_local_at(Section, Slot, Arg) :-
    selected(Section, Slot, Mode),
    conditional_local_var(Section, Slot, Var),
    var_at(Section, Slot, Arg, Var),
    conditional_mode(Mode),
    not head_guard_arg(Mode, Arg).

% DEFINITION, reusable. local_var_at, case 3: local placeholders of
% conditional literals.
local_var_at(Section, Slot, Arg) :- conditional_local_at(Section, Slot, Arg).

% CONSTRAINT. Every local variable of a conditional literal must be bound by
% one of its own conditions.
%   Section, Slot  the conditional literal.
%   Var            a local variable id of it.
%   pruned: :- p(V0) : not q(V0).        no condition binds V0
%   pruned: h :- p(V0,V1) : q(V0).       V1 is local and unbound
%   kept:   :- p(V0) : q(V0).
:- conditional_local_var(Section, Slot, Var),
    not local_condition_bound(Section, Slot, conditional, -1, Var).

% DEFINITION, reusable. conditional_global_var(Section, Slot, Var): Var occurs
% in the conditional literal at that slot and is clause-global.
%   Section, Slot  the selected conditional literal.
%   Var            variable id of it that also occurs outside local
%                  constructs.
% Shared by the constraint below and legality/flow/declarations.lp, which
% applies input/output requirements to exactly these variables.
conditional_global_var(Section, Slot, Var) :-
    conditional_var(Section, Slot, Var),
    not conditional_local_var(Section, Slot, Var).

% CONSTRAINT. Every clause-global variable of a conditional literal must be
% ASP-safe; its own conditions do not ground it for the rest of the clause.
%   Section, Slot  the conditional literal.
%   Var            a clause-global variable id of it.
%   pruned: h(V0) :- p(V0,V1) : q(V1).          V0 is global via the head and
%                                               nothing grounds it
%   kept:   h(V0) :- d(V0), p(V0,V1) : q(V1).
:- conditional_global_var(Section, Slot, Var), not asp_safe(Var).
