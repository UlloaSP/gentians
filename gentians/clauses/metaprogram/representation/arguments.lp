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
1 { var_at(Section, Slot, Arg, Var) : var(Var), Var <= Bound,
    not blocked_binding(Section, Slot, Arg, Var) } 1 :-
    not nominal_bindings,
    not connected_bindings,
    not alias_binding(Section, Slot, Arg),
    arg(Section, Slot, Arg), first_occurrence_bound(Section, Slot, Arg, Bound).

% Optional exact representation for flat modes without local scopes. Type is
% chosen per syntactic id, never a disjoint id namespace per nominal type.
0 { nominal_variable_type(Var, Type): binding_type(Type) } 1 :-
    nominal_bindings, var(Var).
1 { var_at(Section, Slot, Arg, Var): var(Var), Var <= Bound,
    nominal_variable_type(Var, Type) } 1 :-
    nominal_bindings, arg(Section, Slot, Arg), arg_type(Section, Slot, Arg, Type),
    first_occurrence_bound(Section, Slot, Arg, Bound).
:- nominal_variable_type(Var, _), not used_var(Var).

% Optional typed-prefix representation. Body-before-head order is the same
% tuple order as symmetry/variables.lp, including selected rather than merely
% potential positions. An id may be reused with its already-declared type or
% introduced as exactly the next dense id. Legal input/output execution order
% is still proved by legality/flow, independently of the order of mode ids.
binding_prefix_next(Section,Slot,Arg,Next) :-
    connected_bindings, arg(Section,Slot,Arg),
    Last = #max {-1; Var : var_at(S,L,A,Var), (S,L,A)<(Section,Slot,Arg)}, Next = Last + 1.
binding_prefix_candidate(Section,Slot,Arg,Var) :-
    connected_bindings, arg_type(Section,Slot,Arg,Type),
    var_at(S,L,A,Var), arg_type(S,L,A,Type), (S,L,A)<(Section,Slot,Arg).
binding_prefix_candidate(Section,Slot,Arg,Next) :-
    binding_prefix_next(Section,Slot,Arg,Next), var(Next).
1 {var_at(Section,Slot,Arg,Var): binding_prefix_candidate(Section,Slot,Arg,Var)} 1 :-
    connected_bindings, arg(Section,Slot,Arg).

% DEFINITION, local helper. alias_binding(Section,Slot,Arg): this selected
% placeholder is forced equal to an earlier root by an existing body property.
alias_binding(Section,Slot,Arg) :- selected(Section,Slot,Mode), binding_alias(Mode,Arg,_).

% DEFINITION, reusable. var_at/4, alias case: no decision for a forced copy.
% Root is earlier, so its first-occurrence bound also satisfies Arg's bound.
var_at(Section,Slot,Arg,Var) :-
    selected(Section,Slot,Mode), binding_alias(Mode,Arg,Root), var_at(Section,Slot,Root,Var).

% DEFINITION, local helper. distinct_binding(Mode,Earlier,Arg): a flat
% placeholder cannot use the variable already chosen for Earlier. Bridges such
% as irreflexive_pred -> arg_distinct_pred remain owned by their property files.
distinct_binding(Mode,A,B) :- binding_flat_mode(Mode), mode_atom(Mode,Pred,_), arg_distinct_pred(Pred,A,B), A<B.
distinct_binding(Mode,B,A) :- binding_flat_mode(Mode), mode_atom(Mode,Pred,_), arg_distinct_pred(Pred,A,B), B<A.

% DEFINITION, local helper. blocked_binding(Section,Slot,Arg,Var): remove
% that id before choosing Arg. Dependence is strictly on an earlier argument.
blocked_binding(Section,Slot,Arg,Var) :-
    selected(Section,Slot,Mode), distinct_binding(Mode,Earlier,Arg), var_at(Section,Slot,Earlier,Var).

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
