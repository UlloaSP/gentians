% Assign one variable to each flattened placeholder of a selected mode.
% Rendered predicate arity and placeholder count can differ for nested terms.
% Fixed terms live in mode_shape/2 and require no variable assignment.


% DEFINITION, reusable. arg(Section, Slot, Arg): the literal selected at that
% slot has a variable placeholder at Arg.
%   Section  head or body.
%   Slot     slot position inside the section.
%   Arg      zero-based variable-placeholder position of the selected mode
%            (mode_variable_arg/2); constants and fixed terms have none.
% The choice below opens one decision per placeholder. It is also shared by
% pruning/properties/disjoint.lp, project_implies.lp and functional_set.lp,
% which ask "does that literal hold this variable there?" and need to know
% the placeholder exists without naming its variable.
arg(Section, Slot, Arg) :-
    selected(Section, Slot, Mode),
    mode_variable_arg(Mode, Arg).

% CHOICE. Bind every placeholder to exactly one variable.
%   Section, Slot, Arg  the placeholder, as in arg/3.
%   Var                 variable id from var/1 written at that placeholder.
%   Bound               conservative id bound from symmetry/variables.lp:
%                       dense ids grow by their first body-before-head use.
%   allowed: var_at(body,0,0,0), var_at(body,0,1,1)   -> edge(V0,V1)
%   allowed: var_at(body,0,0,0), var_at(body,0,1,0)   -> edge(V0,V0)
%   never:   a placeholder with no var_at atom, or with two of them
% var_at/4 is the second half of the reified clause: nearly every module joins
% on it, and Python's decoder reads it back to render the variables.
% The bound removes only assignments already forbidden by variable symmetry;
% it retains all ids up to the task's #maxv where their first use is possible.
1 { var_at(Section, Slot, Arg, Var) : var(Var), Var <= Bound } 1 :-
    arg(Section, Slot, Arg), first_occurrence_bound(Section, Slot, Arg, Bound).

% DEFINITION, local helper. pooled_body_alternative_var(Slot, Alternative, Var):
% one binding alternative of a body atom grounds Var.
%   Slot         body slot of an atom whose placeholders do not all ground
%                their variable (a pool, or non-invertible arithmetic).
%   Alternative  index of one binding alternative of that atom's mode.
%   Var          variable id at a placeholder that this alternative grounds.
% Used only by pooled_body_missing_var below.
pooled_body_alternative_var(Slot, Alternative, Var) :-
    selected(body, Slot, Mode),
    mode_pool_alternative_arg(Mode, Alternative, Arg),
    var_at(body, Slot, Arg, Var).

% DEFINITION, reusable. pooled_body_missing_var(Slot, Var): the body atom at
% Slot mentions Var but does not ground it.
%   Slot  body slot of a partially binding atom (see above).
%   Var   variable id written in that atom that some alternative leaves
%         ungrounded.
% In q(V0;V1) neither variable occurs in both alternatives; in q(V0+V1) the
% single alternative grounds nothing. Shared because grounding is asked in
% three places: legality/asp_safety.lp (ASP safety) and legality/flow/seeds.lp
% and closure.lp (mode-directed binding) must agree on which atoms bind.
pooled_body_missing_var(Slot, Var) :-
    selected(body, Slot, Mode),
    mode_pool_alternative(Mode, Alternative),
    var_at(body, Slot, _, Var),
    not pooled_body_alternative_var(Slot, Alternative, Var).

% DEFINITION, reusable. arg_type(Section, Slot, Arg, Type): declared type of a
% placeholder of a selected literal.
%   Section, Slot  the selected literal.
%   Arg            variable-placeholder position inside it.
%   Type           nominal type the mode declares there. A position declared
%                  "any" has no fact and therefore never conflicts.
% Lifts mode_arg_type/3 from templates to the selected clause. Shared by
% legality/typing.lp (one type per variable scope) and
% pruning/redundancy/comparisons.lp (whether a "<" mode admits a variable).
arg_type(Section, Slot, Arg, Type) :-
    selected(Section, Slot, Mode),
    mode_arg_type(Mode, Arg, Type).
