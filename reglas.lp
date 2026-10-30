% ==========================================================================
% Legend (representation/schema.lp)
% ==========================================================================

% Optional and cross-module predicate declarations for clause generation.
%
% Clingo's #defined directive only declares that a predicate belongs to the
% program vocabulary. It neither creates facts nor gives the predicate a
% closed-world meaning beyond normal ASP semantics. A declared predicate can
% therefore be empty for a particular task. Python emits most relations below;
% a few are views defined by another metaprogram module. Keeping the declarations
% here makes the Python-to-ASP contract visible in one place and prevents each
% consumer from restating part of that contract.
%
% Identifier conventions used throughout this file:
%   Mode       integer id of one compiled language-bias template.
%   Predicate  integer id of a signed predicate signature; p/n and -p/n differ.
%   Section    head or body.
%   Slot       occurrence position inside a section of the candidate clause.
%   Position   zero-based variable-placeholder position in a mode. For a plain
%              atom (only variables and constants) it is the source argument
%              index, so property facts line up with it; otherwise it is the
%              flattened placeholder index and constants occupy none.
%   Argument   zero-based source-level predicate argument position.
%   Variable   integer id rendered as V0, V1, ...; it is not a ground value.
%   Form       id shared by all elements of one compound head declaration.
%   Condition  zero-based occurrence id inside a conditional or aggregate.
%
% Comment conventions used by every other module. Each rule, choice and
% constraint carries a comment of one of these kinds directly above it:
%   DEFINITION  a rule that derives a view. "reusable" names the modules that
%               consume it and why it is shared; "local helper" is used only
%               inside its own file; "property bridge" derives a weaker
%               property so that the file owning that property prunes for it.
%               Every argument of the head is listed.
%   CHOICE      a generator: it opens the alternatives that models differ in.
%   CONSTRAINT  defines nothing and only removes models. "pruned" and "kept"
%               show rendered candidate clauses (one stable model each) or
%               body fragments. "kept" means that this constraint does not
%               reject the clause; another independent constraint still can.
%               "(policy)" marks a restriction of the enumerator that is not
%               an ASP impossibility or redundancy.
%

% ==========================================================================
% 1. Output
% ==========================================================================

% OUTPUT: the complete reified clause consumed by the prepared Python decoder.
% These signatures control display only; legality and pruning remain in ASP.
#show selected/3.
#show var_at/4.

% ==========================================================================
% 2. Generators: selected/3, var_at/4, clause_body_size/1 (read by Python) and what they depend on
% ==========================================================================

% ----- representation/slots.lp -----

% DEFINITION, reusable. selected(head, Slot, Mode): the head holds Mode at Slot.
%   head  the section; this rule only fills the head.
%   Slot  head position of the member inside its form (0, 1, ...).
%   Mode  id of the compiled language-bias template placed there.
% Every member of the selected form is derived together, which is why a form is
% never a subset choice: "red(V0);green(V0)" appears whole or not at all.
% selected/3 is the core of the reified clause: nearly every module joins on
% it, and Python's decoder reads it back to rebuild the clause.
selected(head, Slot, Mode) :-
    selected_head_form(Form),
    head_form_member(Form, Slot, Mode).

% CHOICE. Fill each body slot with at most one body mode.
%   body  the section; this rule only fills the body.
%   Slot  a body slot from body_slot/1.
%   Mode  any template declared for the body (mode_section(Mode, body)).
%   allowed: selected(body,0,M)                 one literal in slot 0
%   allowed: no selected(body,0,_)              slot 0 left empty
%   never:   selected(body,0,M) and selected(body,0,N) with M != N
% Gaps and slot permutations are removed later by symmetry/slots.lp.
0 { selected(body, Slot, Mode) : mode_section(Mode, body) } 1 :- body_slot(Slot), not body_counts.

% Exact count representation, selected/3 remains the single downstream IR.
body_mode_capacity(Mode,Recall) :- body_counts, mode_section(Mode,body), mode_recall(Mode,Recall), max_body(Max), Recall<=Max.
body_mode_capacity(Mode,Max) :- body_counts, mode_section(Mode,body), mode_recall(Mode,Recall), max_body(Max), Max<Recall.
1 { mode_count(Mode,0..Limit) } 1 :- body_mode_capacity(Mode,Limit).
:- body_counts, max_body(Max), #sum{Count,Mode:mode_count(Mode,Count)} > Max.
mode_start(Mode,Start) :- mode_count(Mode,_), Start=#sum{N,M:mode_count(M,N),M<Mode}.
selected(body,Start+Occurrence,Mode) :-
    mode_count(Mode,Count), mode_start(Mode,Start), Occurrence=0..Count-1.

% CHOICE. Select at most one head form.
%   Form  a declared head form. None selected: the candidate is a constraint.
%   allowed: no selected_head_form atom       -> ":- edge(V0,V1)."
%   allowed: selected_head_form(3)            -> "target(V0) :- edge(V0,V1)."
%   never:   selected_head_form(3) together with selected_head_form(4)
0 { selected_head_form(Form) : head_form(Form) } 1.

% DEFINITION, local helper. head_form(Form): Form is a declared head form.
%   Form  id shared by all members of one compound head declaration.
% Projects head_form_member/3 so the choice below ranges over each form once,
% not once per member.
head_form(Form) :- head_form_member(Form, _, _).

% DEFINITION, reusable domain. body_slot(Slot): Slot is an available body slot.
%   Slot  integer in 0..Max-1, with Max from max_body(Max). Max = 0 leaves no
%         slot, so only bodyless clauses exist.
% Shared because the body choice below opens one decision per slot, and
% representation/tuples.lp quantifies over slots that may be empty in the
% current model.
body_slot(0..Max-1) :- max_body(Max), Max > 0.

% ----- representation/arguments.lp -----

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

% DEFINITION, reusable. var_at/4, alias case: no decision for a forced copy.
% Root is earlier, so its first-occurrence bound also satisfies Arg's bound.
var_at(Section,Slot,Arg,Var) :-
    selected(Section,Slot,Mode), binding_alias(Mode,Arg,Root), var_at(Section,Slot,Root,Var).

% DEFINITION, local helper. blocked_binding(Section,Slot,Arg,Var): remove
% that id before choosing Arg. Dependence is strictly on an earlier argument.
blocked_binding(Section,Slot,Arg,Var) :-
    selected(Section,Slot,Mode), distinct_binding(Mode,Earlier,Arg), var_at(Section,Slot,Earlier,Var).

% ----- representation/variables.lp -----

% Variable occurrence and repeated-name relations; ids denote syntax, not values.

% DEFINITION, reusable. used_var(Var): Var occurs somewhere in the clause.
%   Var  variable id (rendered V<Var>) held by at least one placeholder.
% Shared because symmetry/variables.lp orders exactly the used ids and
% pruning/policies/singletons.lp inspects each used id once.
used_var(Var) :- var_at(_, _, _, Var).

% ----- representation/arguments.lp -----

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

% DEFINITION, local helper. alias_binding(Section,Slot,Arg): this selected
% placeholder is forced equal to an earlier root by an existing body property.
alias_binding(Section,Slot,Arg) :- selected(Section,Slot,Mode), binding_alias(Mode,Arg,_).

% ----- representation/slots.lp -----

% DEFINITION, reusable domain. var(Var): Var is an available variable id.
%   Var  integer in 0..Max-1, with Max from max_vars(Max); rendered as V<Var>.
%        It names a syntactic variable, never a ground value.
% Shared because representation/arguments.lp draws every var_at binding from
% this domain and symmetry/variables.lp forbids skipping ids inside it.b
var(0..Max-1) :- max_vars(Max).

% ----- symmetry/variables.lp -----

% DEFINITION, reusable domain bound. first_occurrence_bound(Section, Slot,
% Arg, Bound): largest variable id that could occur at this position under
% the dense, first-occurrence ordering enforced below.
%   Section, Slot, Arg  a possible placeholder, in Clingo's body-before-head
%                       tuple order (not section_order's head-before-body).
%   Bound               number of possible earlier placeholder positions.
% If id V occurs here, ids 0..V-1 have earlier first occurrences. One position
% holds one id, so V cannot exceed the number of possible earlier positions.
% Counting the union of all modes is conservative when slots are empty or
% the selected mode has fewer placeholders. The existing ordering constraints
% still reject impossible assignments inside this overapproximation.
% Consumed by representation/arguments.lp to omit choices that these same
% symmetry rules would reject. This introduces no task limit or new pruning.
first_occurrence_bound(Section, Slot, Arg, Bound) :-
    potential_var_pos(Section, Slot, Arg),
    Bound = #count {
        S, L, A : potential_var_pos(S, L, A), (S, L, A) < (Section, Slot, Arg)
    }.

% Choose dense variable ids ordered by their first occurrence.
% These comparisons order syntactic ids, not their object-level values.

% DEFINITION, local helper. potential_var_pos(body, Slot, Arg): a variable
% placeholder that some declared body mode could place at this slot.
%   Slot  any available body slot, including an unoccupied one.
%   Arg   an actual mode_variable_arg position, not a predicate arity index.
% The union across modes overapproximates actual positions. Constants do not
% add positions, and gaps in placeholder indexes are not counted as bindings.
% Used only by first_occurrence_bound below.
potential_var_pos(body, Slot, Arg) :-
    body_slot(Slot), mode_section(Mode, body), mode_variable_arg(Mode, Arg).

% DEFINITION, local helper. potential_var_pos(head, Slot, Arg): a variable
% placeholder of a member of some declared complete head form.
%   Slot  the member's position within its head form.
%   Arg   a variable-placeholder position, including variable head guards.
% All forms contribute possible positions, even when another form or no head
% is selected. Used only by first_occurrence_bound below.
potential_var_pos(head, Slot, Arg) :-
    head_form_member(_, Slot, Mode), mode_variable_arg(Mode, Arg).

% ----- representation/arguments.lp -----

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

% DEFINITION, local helper. distinct_binding(Mode,Earlier,Arg): a flat
% placeholder cannot use the variable already chosen for Earlier. Bridges such
% as irreflexive_pred -> arg_distinct_pred remain owned by their property files.
distinct_binding(Mode,A,B) :- binding_flat_mode(Mode), mode_atom(Mode,Pred,_), arg_distinct_pred(Pred,A,B), A<B.
distinct_binding(Mode,B,A) :- binding_flat_mode(Mode), mode_atom(Mode,Pred,_), arg_distinct_pred(Pred,A,B), B<A.

% ----- pruning/properties/irreflexive.lp -----

% Closed-world irreflexive predicate property.
%
% This file owns irreflexive knowledge: reject positive self-pairs Pred(Var, Var)
% and export the equivalent argument-distinct property for binary predicates.
% Stronger properties such as asymmetric, acyclic, and strict_order derive
% irreflexive_pred(Pred) in their own files.

% DEFINITION, reusable property bridge. arg_distinct_pred(Pred, 0, 1): the two
% arguments of an irreflexive binary predicate always differ.
%   Pred  signed predicate id of an irreflexive binary predicate.
%   0, 1  its two argument positions.
% Lets pruning/properties/arg_distinct.lp apply its checks (negated atoms and
% aggregate conditions) without repeating them here.
arg_distinct_pred(Pred, 0, 1) :- irreflexive_pred(Pred).

% ----- pruning/properties/acyclic.lp -----

% Acyclic relations exclude self-pairs, reversed pairs and positive triangles.
% The first two checks are delegated to irreflexive/antisymmetric properties.
% A negated back-edge over a positive two-step path is redundant.

% DEFINITION, reusable property bridge. irreflexive_pred(Pred): Pred never
% relates a value to itself.
%   Pred  signed predicate id of a binary closed predicate proved acyclic.
% An acyclic relation has no cycle of length 1. Deriving the base property
% lets pruning/properties/irreflexive.lp own the self-pair check instead of
% repeating it here.
irreflexive_pred(Pred) :- acyclic_pred(Pred).

% ----- pruning/properties/asymmetric.lp -----

% Closed-world asymmetric predicate property.
%
% Python emits asymmetric_pred(Pred) when binary predicate Pred never has both
% Pred(X, Y) and Pred(Y, X) in observed facts. Asymmetry implies irreflexivity
% and antisymmetry, so this file exports those base-property atoms instead of
% duplicating their constraints here.

% DEFINITION, reusable property bridge. irreflexive_pred(Pred): Pred never
% relates a value to itself.
%   Pred  signed predicate id of a binary closed predicate proved asymmetric.
% Pred(X,X) would be its own reverse, which asymmetry forbids. The self-pair
% check is owned by pruning/properties/irreflexive.lp.
irreflexive_pred(Pred) :- asymmetric_pred(Pred).

% ----- pruning/properties/strict_order.lp -----

% DEFINITION, reusable property bridge. acyclic_pred(Pred): Pred has no
% directed cycle.
%   Pred  signed predicate id of a binary closed predicate proved a strict
%         order.
% The cycle checks are owned by pruning/properties/acyclic.lp, which in turn
% derives irreflexive_pred and antisymmetric_pred.
acyclic_pred(Pred) :- strict_order_pred(Pred).

% ----- representation/slots.lp -----

% DEFINITION, reusable, but its consumer is Python rather than another module.
% clause_body_size(Size): total body size of the candidate clause.
%   Size  body_count plus selected_condition_count: occupied body slots plus
%         every condition attached to a selected mode, in head or body.
% Derived only when Python emits enumerate_by_size. generator.py grounds once
% and then solves one stratum per Size, passing this atom as an assumption, so
% incremental generation receives clauses grouped by size.
clause_body_size(Body+Conditions) :-
    enumerate_by_size, body_count(Body), selected_condition_count(Conditions).

% ----- representation/conditionals.lp -----

% Conditional conclusions, condition variables and predicate dependencies.
% The condition count includes attachments in both head and body. Local/global
% scope is resolved separately in legality/scopes.lp.

% DEFINITION, reusable. selected_condition_count(Count): how many conditions
% the whole clause attaches.
%   Count  sum, over every selected mode in head and body, of its
%          mode_condition_count. "p(V0):q(V0),r(V0)" contributes 2; a plain
%          atom contributes 0. Always defined; 0 when nothing is attached.
% Shared by representation/slots.lp (clause_body_size) and
% legality/clause_shape.lp (body budget): both count a condition as one body
% literal.
selected_condition_count(Count) :-
    Count = #sum {
        Conditions, Section, Slot, Mode :
        selected(Section, Slot, Mode),
        mode_condition_count(Mode, Conditions)
    }.

% ----- representation/slots.lp -----

% Finite variable/body-slot domains and complete head-form selection.
% A selected head form activates all its members; it is never a subset choice.
% clause_body_size includes attached conditions and supplies incremental solves.
% Gapless slots and canonical ordering are enforced in symmetry/slots.lp.

% DEFINITION, reusable. body_count(Count): how many body slots are occupied.
%   Count  integer in 0..max_body: number of Slot with selected_slot(body, Slot).
%          Conditions attached to a conditional are not slots and are excluded.
% Shared because two consumers need the same total: clause_body_size below
% and the body budget of legality/clause_shape.lp.
body_count(Count) :- Count = #count{Slot : selected_slot(body, Slot)}.

% DEFINITION, reusable. selected_slot(Section, Slot): that slot is occupied.
%   Section  head or body.
%   Slot     slot position inside the section.
% Drops the Mode of selected/3. Shared because body_count above, the empty
% clause check in legality/clause_shape.lp, the headless checks in
% legality/invention.lp and pruning/task/optional_constraints.lp, and the gap
% check in symmetry/slots.lp only ask whether a slot is used, not by what.
selected_slot(Section, Slot) :- selected(Section, Slot, _).

% ==========================================================================
% 3. Constraints, each followed by the views only it needs; shared views sink below their last user
% ==========================================================================

% ----- legality/aggregates.lp -----

% Local variables need a positive atom or a Clingo-proved comparison binding
% in their own element.
% Clause-global occurrences need independent ASP-safe support. An aggregate
% result cannot make its own condition safe by circular assignment.

% The older single-condition equality-output subset retains its canonical
% local tuple projection and associated search-space restrictions.

% CONSTRAINT. Every tuple term of an aggregate must occur in a condition of
% the same aggregate.
%   Slot  body slot of an aggregate of the single-element subset.
%   Var   variable id written as a tuple term.
%   pruned: h(V2) :- #count{V0 : p(V1)} = V2.    V0 is counted but never bound
%   kept:   h(V2) :- #count{V0 : p(V0)} = V2.
:- aggregate_tuple_var(Slot, Var), not aggregate_condition_var(Slot, Var).

% CONSTRAINT. A local variable of an aggregate element must be bound inside
% that same element, by a positive atom condition or a Clingo-proved
% comparison output.
%   Slot      body slot of any aggregate.
%   Element   index of the element that owns the placeholder.
%   Position  flattened placeholder position inside that element.
%   Var       variable id there that occurs nowhere outside local interiors.
%   pruned: :- q(V0), #count{V1 : not p(V1)} = V0.      V1 only under negation
%   pruned: :- q(V0), #count{V1 : p(V1) ; V2 : not r(V2)} = V0.
%                                  V2 is unbound in element 1; element 0 is fine
%   kept:   :- q(V0), #count{V1 : p(V1)} = V0.
:- aggregate_element_arg(Slot, Element, Position),
    var_at(body, Slot, Position, Var),
    not global_context_var(Var),
    not local_condition_bound(body, Slot, aggregate, Element, Var).

% A global element variable needs an independent positive body atom: the
% aggregate's own output cannot ground it (#count{X:p(X)}=X is unsafe).
% CONSTRAINT. Any placeholder inside any aggregate element, tuple or
% condition, that holds a clause-global variable requires that variable in a
% positive plain body atom.
%   Slot, Element, Position  the interior placeholder.
%   Var                      clause-global variable id written there.
% A variable is clause-global as soon as it occurs outside aggregate
% interiors, which includes the result and the guards of the aggregate itself:
%   pruned: :- #count{V0 : p(V0)} = V0.                 V0 is also the result
%   pruned: :- #count{V0 : p(V0,V1)} = V1.              V1 would ground itself
%   pruned: h(V1,V2) :- #count{V0 : p(V0,V1)} = V2.     V1 only in the head
%   pruned: h(V0,V1) :- #count{V0 : p(V0)} = V1.        a global tuple term
%   kept:   h(V1,V2) :- q(V1), #count{V0 : p(V0,V1)} = V2.
:- aggregate_element_arg(Slot, Element, Position),
    var_at(body, Slot, Position, Var),
    global_context_var(Var), not normal_positive_body_var(Var).

% CONSTRAINT. A non-producing guard variable of an aggregate must be ASP-safe.
%   Var  variable id the aggregate only compares against (a bound).
%   pruned: :- #count{V0 : p(V0)} > V1.            nothing grounds V1
%   kept:   :- q(V1), #count{V0 : p(V0)} > V1.
:- aggregate_guard_var(_, Var), not asp_safe(Var).

% ----- representation/aggregates.lp -----

% DEFINITION, reusable. aggregate_guard_var(Slot, Variable): a variable the
% aggregate at body Slot only compares against.
%   Slot      body slot of an aggregate.
%   Variable  variable id at a non-producing guard: V1 in "#count{...} > V1"
%             or either bound of "V1 <= #count{...} <= V2".
% Consumed by legality/aggregates.lp, which requires it to be safe elsewhere.
aggregate_guard_var(Slot, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_guard_arg(Mode, Position),
    var_at(body, Slot, Position, Variable).

% ----- legality/asp_safety.lp -----

% CONSTRAINT. Every clause-global head variable must be ASP-safe.
%   Var  variable id of a global head occurrence.
%   pruned: h(V0,V1) :- p(V0).          nothing grounds V1
%   pruned: h(V0) :- not p(V0).         negation grounds nothing
%   kept:   h(V0,V1) :- p(V0), q(V1).
:- head_var(Var), not asp_safe(Var).

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

% DEFINITION, local helper. negated_var(Var): Var occurs in a default-negated
% plain body atom.
%   Var  variable id written in "not p(...)" or "not not p(...)".
% Used only by the negation safety constraint below.
negated_var(Var) :-
    negative_body_literal(Slot, Mode, _, _),
    var_at(body, Slot, _, Var).

% CONSTRAINT. Every variable a comparison reads must be ASP-safe.
%   Var  variable id at a non-output comparison placeholder.
%   pruned: :- p(V0), V0 < V1.           V1 is only compared
%   kept:   :- p(V0), p(V1), V0 < V1.
:- comparison_var(Var), not asp_safe(Var).

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

% CONSTRAINT. Every operand of an arithmetic literal must be ASP-safe.
%   Var  variable id of an operand.
%   pruned: h(V2) :- p(V0), V0+V1=V2.    V1 is never grounded
%   kept:   h(V2) :- p(V0), p(V1), V0+V1=V2.
:- arithmetic_operand_var(Var), not asp_safe(Var).

% DEFINITION, local helper. arithmetic_operand_var(Var): Var is an operand of
% a body arithmetic literal.
%   Var  variable id on the left or right of "Left op Right = Result".
% Used only by the operand safety constraint below.
arithmetic_operand_var(Var) :-
    selected(body, Slot, Mode),
    arithmetic_mode(Mode),
    arithmetic_operand(Slot, _, Var).

% ----- legality/clause_shape.lp -----

% Clause-wide body budget and exclusion of the completely empty clause.

% CONSTRAINT. Body literals plus attached conditions must fit in max_body.
%   Body        number of occupied body slots.
%   Conditions  conditions attached to selected modes, in head and body.
%   Max         the task's body limit (#maxbl).
% Slots alone can never exceed Max; the conditions are what can overflow.
% With #maxbl(2):
%   pruned: :- p(V0), q(V0) : r(V0).     2 literals + 1 condition = 3
%   kept:   :- q(V0) : r(V0).            1 literal  + 1 condition = 2
:- body_count(Body),
    selected_condition_count(Conditions),
    max_body(Max),
    Body + Conditions > Max.

% CONSTRAINT. The clause must have a head or at least one body literal.
%   pruned: the model with no selected/3 atom at all (the empty clause)
%   kept:   "h(V0)." with an empty body, or ":- p(V0)." with no head
:- not selected_slot(head, _), not selected_slot(body, _).

% ----- legality/flow/requirements.lp -----

% Reject unmet inputs and outputs after the positive fixed point.
% Default-negated and conditional literals never produce global variables.
%
% The examples assume these declarations unless they state others:
%   #modeh(1,target(var(node,input),var(node,output))).
%   #modeb(2,edge(var(node,input),var(node,output))).

% CONSTRAINT. A clause-global variable at an input position of a conditional
% literal must be flow_bound.
%   Var  such a variable id.
% With #modeb(1,ok(var(node,input)):node(var(node,any))); V0 is global in
% both clauses because it also occurs in edge:
%   pruned: :- edge(V0,V1), ok(V0) : node(V2).                  no seed binds V0
%   kept:   target(V0,V1) :- edge(V0,V1), ok(V0) : node(V2).    V0 is a head input
:- conditional_global_input_var(Var), not flow_bound(Var).

% ----- legality/flow/declarations.lp -----

% Classify directed modes, count required inputs and expose conditional roles.
% Counts are positions, not distinct variables: repeated input names still fill
% every declared input position.

% DEFINITION, reusable. conditional_global_input_var(Var): a conditional
% literal reads the clause-global variable Var at a position declared input.
%   Var  variable id that is global to the clause (legality/scopes.lp) and
%        sits at an input placeholder of a selected conditional, in head or
%        body.
% Consumed by legality/flow/requirements.lp: such an input must be bound.
conditional_global_input_var(Var) :-
    selected(Section, Slot, Mode),
    conditional_global_var(Section, Slot, Var),
    mode_arg_direction(Mode, Arg, input),
    var_at(Section, Slot, Arg, Var).

% ----- legality/flow/requirements.lp -----

% CONSTRAINT. A clause-global variable at an output position of a body
% conditional must be produced by another literal; the conditional itself
% produces nothing.
%   Var  such a variable id.
% With #modeb(1,reach(var(node,output)):node(var(node,any))):
%   pruned: target(V0,V1) :- reach(V1) : node(V2).     V1 is global via the
%                                                      head; nothing produces it
%   kept:   target(V0,V1) :- edge(V0,V1), reach(V1) : node(V2).   edge produces V1
:- conditional_global_output_var(body, Var), not flow_produced(Var).

% A head output is also satisfied by an input position of the same head.
% CONSTRAINT. A clause-global variable at an output position of a head
% conditional must be produced by the body or be a head input.
%   Var  such a variable id.
% With #modeh(1,mark(var(node,output)):node(var(node,any))),
% #modeb(1,seen(var(node,any))) and #modeb(1,start(var(node,output))); V0 is
% global in both clauses because it also occurs in the body:
%   pruned: mark(V0) : node(V1) :- seen(V0).     "any" binds V0 without producing it
%   kept:   mark(V0) : node(V1) :- start(V0).    start outputs V0
:- conditional_global_output_var(head, Var),
    not flow_produced(Var),
    not head_input_var(Var).

% ----- legality/flow/declarations.lp -----

% DEFINITION, reusable. conditional_global_output_var(Section, Var): a
% conditional literal declares the clause-global variable Var as output.
%   Section  head or body: where the conditional is selected. The requirement
%            differs per section, so it is kept.
%   Var      clause-global variable id at an output placeholder of it.
% Consumed by legality/flow/requirements.lp. A conditional never produces a
% global variable, so another literal must produce it.
conditional_global_output_var(Section, Var) :-
    selected(Section, Slot, Mode),
    conditional_global_var(Section, Slot, Var),
    mode_arg_direction(Mode, Arg, output),
    var_at(Section, Slot, Arg, Var).

% ----- legality/flow/requirements.lp -----

% CONSTRAINT. Every selected arithmetic literal must become ready: both
% operands flow_bound.
%   Slot  body slot of the arithmetic literal.
% With #modeb(1,num(var(numeric,any))):
%   pruned: :- num(V0), V0+V1=V2.           V1 is never bound
%   kept:   :- num(V0), num(V1), V0+V1=V2.
:- selected(body, Slot, Mode), arithmetic_mode(Mode), not ready_arithmetic(Slot).

% CONSTRAINT. Every variable a comparison reads (a non-output placeholder)
% must be flow_bound.
%   Slot, Arg  the comparison placeholder.
%   Var        variable id written there.
% With #modeb(1,num(var(numeric,any))):
%   pruned: :- num(V0), V0 < V1.            V1 is never bound
%   kept:   :- num(V0), num(V1), V0 < V1.
:- selected(body, Slot, Mode),
    comparison_mode(Mode),
    var_at(body, Slot, Arg, Var),
    not mode_arg_direction(Mode, Arg, output),
    not flow_bound(Var).

% ----- representation/operators.lp -----

% DEFINITION, reusable. comparison_mode(Mode): Mode is a comparison literal,
% simple or chained.
%   Mode  id of a template of kind comparison.
% Shared by legality/asp_safety.lp and legality/flow/requirements.lp, which
% require compared variables to be bound elsewhere.
comparison_mode(Mode) :- mode_kind(Mode, comparison).

% ----- legality/flow/requirements.lp -----

% CONSTRAINT. Every selected value-producing comparison must become ready:
% all its non-output placeholders flow_bound.
%   Slot  body slot of the comparison.
% With #modeb(1,num(var(numeric,any))) and an assigning comparison rendered
% "V1 = V0 + 1", whose left side is declared output and right side input:
%   pruned: :- V1 = V0 + 1.                 V0 is never bound
%   kept:   :- num(V0), V1 = V0 + 1.
:- selected(body, Slot, Mode),
   relation_output_mode(Mode),
   not ready_relation(Slot).

% CONSTRAINT. Every selected directed body literal must become ready: all its
% input positions flow_bound.
%   Slot  body slot of the directed literal.
%   pruned: target(V0,V1) :- edge(V2,V1).                V2 is never bound
%   pruned: :- edge(V0,V1), edge(V1,V0).                 an unseeded input cycle
%   kept:   target(V0,V1) :- edge(V0,V1).                V0 is a head input
%   kept:   target(V0,V1) :- edge(V0,V2), edge(V2,V1).   a chain from V0
:- selected(body, Slot, Mode), directed_mode(Mode), not ready_literal(Slot).

% CONSTRAINT. Every output position of a non-conditional head literal must be
% produced by the body or coincide with a head input.
%   Slot, Arg  the head placeholder declared output.
%   Var        variable id written there.
%   pruned: target(V0,V1) :- edge(V0,V2).   V1 is never produced
%   kept:   target(V0,V1) :- edge(V0,V1).   edge produces V1
%   kept:   target(V0,V0) :- edge(V0,V1).   V0 is an input of the same head
:- selected(head, Slot, Mode),
    not conditional_mode(Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(head, Slot, Arg, Var),
    not flow_produced(Var),
    not head_input_var(Var).

% ----- legality/flow/closure.lp -----

% Positive least fixed point of readiness and production. No body order is
% imposed. flow_produced implies flow_bound; any positions of positive normal
% atoms may bind without satisfying an output requirement.
%
% Mode readiness is not grounding safety. A relation output is also asp_safe
% only when its other arguments are asp_safe, never through a head input or
% through the output itself:
%   h(V0) :- V0=(V0*V0)+1.            rejected: V0 is only a head input
%   h(V0) :- d(V0), V1=(V0*V1)+1.     rejected: V1 would ground itself

% DEFINITION, reusable. ready_literal(Slot): the directed literal at body Slot
% has all its inputs available.
%   Slot  body slot of a directed mode in which every placeholder declared
%         input holds a flow_bound variable. A mode with no inputs is ready
%         at once.
% The count ranges over (position, variable) pairs, so an input name repeated
% at two input positions fills both. Shared by the two rules below and by
% legality/flow/requirements.lp, which rejects a directed literal that never
% becomes ready.
ready_literal(Slot) :-
    selected(body, Slot, Mode),
    input_count(Mode, Count),
    Count <= #count{
        Arg, Var : mode_arg_direction(Mode, Arg, input),
                  var_at(body, Slot, Arg, Var),
                  flow_bound(Var)
    }.

% DEFINITION, reusable. flow_bound(Var): Var has a value available to feed an
% input position.
%   Var  variable id.
% Weaker than flow_produced: it does not satisfy an output requirement.
% Defined here and in legality/flow/seeds.lp; consumed by the readiness rules
% of this file and by legality/flow/requirements.lp.
% Case: an "any" placeholder of a ready positive plain atom binds its
% variable, provided the atom grounds it in every binding alternative.
%   Slot  body slot of that ready atom.
%   Mode  its positive plain (binding) mode.
%   Arg   a placeholder of it declared any.
flow_bound(Var) :-
    ready_literal(Slot),
    selected(body, Slot, Mode),
    binding_mode(Mode),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Slot, Arg, Var),
    not pooled_body_missing_var(Slot, Var).

% DEFINITION, reusable. flow_bound(Variable), closing case: whatever is
% produced is also bound, so it can feed the inputs of other literals.
flow_bound(Variable) :- flow_produced(Variable).

% ----- legality/flow/seeds.lp -----

% DEFINITION, reusable. flow_bound(Var), seed 1: every head input is bound
% from the start. See legality/flow/closure.lp for the meaning of flow_bound.
flow_bound(Var) :- head_input_var(Var).

% DEFINITION, reusable. flow_bound(Var), seed 2: an "any" placeholder of an
% undirected positive plain body atom binds its variable unconditionally.
%   Slot  body slot of that atom.
%   Mode  its mode: binding (positive plain atom) and not directed, so it has
%         no input to wait for.
%   Arg   a placeholder of it declared any.
%   Var   variable id written there, grounded in every binding alternative.
% With node(any), "node(V0)" binds V0. A directed atom binds its "any"
% positions only once ready (closure.lp).
flow_bound(Var) :-
    selected(body, Slot, Mode),
    binding_mode(Mode),
    not directed_mode(Mode),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Slot, Arg, Var),
    not pooled_body_missing_var(Slot, Var).

% ----- legality/flow/closure.lp -----

% DEFINITION, reusable. flow_produced(Var): some literal outputs Var.
%   Var  variable id.
% Only a produced variable satisfies a declared output. Defined here and in
% legality/flow/seeds.lp; consumed by the last rule of this file and by
% legality/flow/requirements.lp.
% Case 1: an output placeholder of a ready positive plain atom. With
% edge(input,output), "edge(V0,V1)" produces V1 once V0 is bound.
%   Slot  body slot of that ready atom.
%   Mode  its positive plain (binding) mode.
%   Arg   a placeholder of it declared output.
flow_produced(Var) :-
    ready_literal(Slot),
    selected(body, Slot, Mode),
    binding_mode(Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var),
    not pooled_body_missing_var(Slot, Var).

% DEFINITION, reusable. flow_produced(Result), case 2: the result of a ready
% arithmetic literal.
%   Slot    body slot of that literal.
%   Result  variable id of its result.
flow_produced(Result) :-
    ready_arithmetic(Slot),
    arithmetic_result(Slot, Result).

% DEFINITION, reusable. flow_produced(Var), case 3: an output placeholder of
% a ready value-producing comparison.
%   Slot  body slot of that comparison.
%   Arg   a placeholder of it declared output.
flow_produced(Var) :-
    ready_relation(Slot),
    selected(body, Slot, Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var).

% ----- legality/flow/seeds.lp -----

% DEFINITION, reusable. flow_produced(Var), seed 1: the equality output of any
% body aggregate is produced. See legality/flow/closure.lp for flow_produced.
flow_produced(Var) :- aggregate_output_var(_, Var).
% DEFINITION, reusable. flow_produced(Var), seed 2: the result of a
% single-element equality aggregate is produced.
flow_produced(Var) :- aggregate_result_var(_, Var).

% ----- legality/flow/closure.lp -----

% DEFINITION, reusable. ready_arithmetic(Slot): the arithmetic literal at body
% Slot can be evaluated.
%   Slot  body slot of "Left op Right = Result" whose two operands are
%         flow_bound.
% Shared by the next rule and by legality/flow/requirements.lp.
ready_arithmetic(Slot) :-
    selected(body, Slot, Mode),
    arithmetic_mode(Mode),
    arithmetic_operand(Slot, left, Left),
    arithmetic_operand(Slot, right, Right),
    flow_bound(Left),
    flow_bound(Right).

% DEFINITION, reusable. ready_relation(Slot): the value-producing comparison
% at body Slot has all its non-output placeholders bound.
%   Slot  body slot of a relation_output_mode in which every variable
%         placeholder not declared output holds a flow_bound variable.
% Shared by the next rule and by legality/flow/requirements.lp.
ready_relation(Slot) :-
    selected(body, Slot, Mode),
    relation_output_mode(Mode),
    relation_input_count(Mode, Count),
    Count <= #count {
        Arg, Var : mode_variable_arg(Mode, Arg),
                  not mode_arg_direction(Mode, Arg, output),
                  var_at(body, Slot, Arg, Var),
                  flow_bound(Var)
    }.

% ----- legality/flow/declarations.lp -----

% DEFINITION, reusable. input_count(Mode, Count): how many inputs a directed
% mode requires.
%   Mode   id of a directed mode.
%   Count  number of its placeholder positions declared input; 0 for a mode
%          with outputs only. Positions are counted, not distinct variables.
% Consumed by legality/flow/closure.lp, which makes a literal ready once that
% many input positions hold bound variables.
input_count(Mode, Count) :-
    directed_mode(Mode),
    Count = #count{Arg : mode_arg_direction(Mode, Arg, input)}.

% DEFINITION, reusable. directed_mode(Mode): Mode declares a data direction.
%   Mode  id of a non-conditional template with at least one input or output
%         placeholder. A mode whose placeholders are all "any" is undirected.
% Shared by input_count below, legality/flow/seeds.lp (an undirected atom binds
% unconditionally) and legality/flow/requirements.lp (a directed literal must
% become ready).
% Case 1: the mode has an input placeholder.
directed_mode(Mode) :- mode_arg_direction(Mode, _, input), not conditional_mode(Mode).

% DEFINITION, reusable. Same predicate. Case 2: the mode has an output
% placeholder.
directed_mode(Mode) :- mode_arg_direction(Mode, _, output), not conditional_mode(Mode).

% ----- legality/invention.lp -----

% CONSTRAINT. A clause defining an invented predicate may read invented
% predicates of strictly earlier layers only.
%   HeadPred, HeadLayer  invented predicate in the head and its layer.
%   BodyPred, BodyLayer  invented predicate the clause reads and its layer.
% With inv1 declared at layer 0 and inv2 at layer 1:
%   pruned: inv1(V0) :- d(V0), inv2(V0).     a later layer
%   pruned: inv2(V0) :- e(V0,V1), inv2(V1).  its own layer: no recursion
%   kept:   inv2(V0) :- d(V0), inv1(V0).     an earlier layer
:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, HeadLayer),
    body_dependency(BodyPred),
    invented_pred(BodyPred, BodyLayer),
    BodyLayer >= HeadLayer.

% CONSTRAINT. A clause defining an invented predicate may not read an
% ordinary learnable predicate (one with a head mode that is not invented).
%   HeadPred  invented predicate in the head.
%   BodyPred  predicate the clause reads.
% With target learnable, inv1 invented and d background:
%   pruned: inv1(V0) :- target(V0).       target could itself depend on inv1
%   kept:   inv1(V0) :- d(V0).
%   kept:   target(V0) :- inv1(V0).       the head is not invented
:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, _),
    body_dependency(BodyPred),
    learnable_head_pred(BodyPred),
    not invented_pred(BodyPred, _).

% A default-negated head `not e` depends on e and does not define it.
% DEFINITION, local helper. learnable_head_pred(Pred): the language bias lets
% some clause define Pred.
%   Pred  signed predicate id of a head template that is not default negated.
% It is a property of the task, not of the current model: it holds whether or
% not that head is selected. Used only by the second constraint below.
learnable_head_pred(Pred) :-
    mode_section(Mode, head),
    mode_atom(Mode, Pred, _),
    not negative_mode(Mode).

% CONSTRAINT. A headless clause may not read an invented predicate.
%   Pred  invented predicate the clause reads.
%   pruned: :- d(V0), inv1(V0).
%   kept:   :- d(V0), target(V0).
%   kept:   target(V0) :- inv1(V0).       it has a head
:- not selected_slot(head, _),
    body_dependency(Pred),
    invented_pred(Pred, _).

% Invented definitions use earlier invention layers or background predicates.
% Calling ordinary learnable predicates could introduce indirect cycles.
% Headless clauses cannot consume invented predicates under this language policy.
% Every body occurrence counts: ordinary literals, conditions, and the atoms and
% conditions of every aggregate form.
%   ha(X) :- d(X), hb(X).                 pruned when hb is not an earlier layer
%   ha(X) :- d(X), 1<={hb(Y):d(Y)}.       pruned for the same reason
%   :- 1<={hb(X):d(X)}.                   pruned: a constraint uses hb

% DEFINITION, local helper. body_dependency(Pred): the candidate clause reads
% predicate Pred.
%   Pred  signed predicate id that occurs anywhere the clause depends on it,
%         under either polarity.
% Collects every way a clause can read a predicate so the three constraints
% below test one relation. Used only in this file.
% Case 1: a plain body atom, positive or default negated.
body_dependency(Pred) :- normal_literal(body, _, _, Pred, _).

% DEFINITION, local helper. Same predicate. Case 2: a conditional construct:
% the conclusion of a body conditional, or a condition attached in head or
% body (representation/conditionals.lp).
body_dependency(Pred) :- conditional_dependency(_, _, Pred).

% DEFINITION, local helper. Same predicate. Case 3: a condition atom of a
% body aggregate of the single-element equality subset.
body_dependency(Pred) :-
    selected(body, _, Mode),
    aggregate_condition_atom(Mode, _, Pred, _).

% DEFINITION, local helper. Same predicate. Case 4: the conclusion atom of an
% element of a body set aggregate, as hb in "1 <= {hb(Y) : d(Y)}".
body_dependency(Pred) :-
    selected(body, _, Mode),
    aggregate_element_atom(Mode, _, Pred, _).

% DEFINITION, local helper. Same predicate. Case 5: a condition atom of any
% element of any body aggregate.
body_dependency(Pred) :-
    selected(body, _, Mode),
    aggregate_element_condition_atom(Mode, _, _, Pred, _).

% ----- representation/conditionals.lp -----

% DEFINITION, reusable. conditional_dependency(Section, Slot, Pred): the
% literal at that slot makes the clause depend on Pred through a conditional
% construct.
%   Section  head or body: where the construct is selected.
%   Slot     its slot.
%   Pred     signed predicate id the clause reads there.
% Consumed by legality/invention.lp, which must see every predicate a clause
% reads, not only its plain body atoms.
% Case 1: the conclusion of a body conditional, as p in ":- p(V0) : q(V0)".
conditional_dependency(body, Slot, Pred) :-
    selected(body, Slot, Mode),
    conditional_mode(Mode), mode_atom(Mode, Pred, _).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: an atom condition of a conditional in either section, as q in
% "p(V0) : q(V0)". A condition is read even when it sits in the head.
conditional_dependency(Section, Slot, Pred) :-
    selected(Section, Slot, Mode),
    conditional_condition(Mode, _, Pred, _).

% DEFINITION, reusable. Same predicate and arguments.
% Case 3: an atom condition of a choice or aggregate head element, as q in
% "{p(V0) : q(V0)}".
conditional_dependency(head, Slot, Pred) :-
    selected(head, Slot, Mode),
    head_aggregate_condition_atom(Mode, _, Pred).

% ----- legality/labels.lp -----

% CONSTRAINT. Within one head form, placeholders with the same label must hold
% the same variable.
%   Form, Label  the head form and the shared label.
%   Left, Right  the two variable ids found under that label.
% With #modeh(1,red(var(node,input,x));green(var(node,input,x))):
%   pruned: red(V0);green(V1) :- node(V0), node(V1).
%   kept:   red(V0);green(V0) :- node(V0).
:- head_label_var(Form, Label, Left),
    head_label_var(Form, Label, Right),
    Left != Right.

% CONSTRAINT. Within one head form, placeholders with different labels must
% hold different variables.
%   Form                   the head form.
%   LeftLabel, RightLabel  two distinct labels; "<" lists each pair once.
%   Var                    the variable id found under both.
% With #modeh(1,from(var(node,input,a));to(var(node,input,b))):
%   pruned: from(V0);to(V0) :- node(V0).
%   kept:   from(V0);to(V1) :- edge(V0,V1).
:- head_label_var(Form, LeftLabel, Var),
    head_label_var(Form, RightLabel, Var),
    LeftLabel < RightLabel.

% Labels constrain identity within a mode and across one complete head form.
% Equal labels share a variable; different labels must use different variables.

% DEFINITION, local helper. head_label_var(Form, Label, Var): inside the
% selected head form, a placeholder labelled Label holds Var.
%   Form   id of the selected compound head form.
%   Label  source label of the placeholder, such as x in var(node,input,x).
%   Var    variable id written at that placeholder, in any member of the form.
% Gathers labels across all members of one head, which no single mode can see.
% Used only by the first two constraints below.
head_label_var(Form, Label, Var) :-
    selected_head_form(Form),
    head_arg_label(Form, Mode, Arg, Label),
    selected(head, Slot, Mode),
    var_at(head, Slot, Arg, Var).

% CONSTRAINT. Within one literal, placeholders with the same label must hold
% the same variable.
%   Section, Slot  the literal.
%   Label          the shared label.
%   Left, Right    the two variable ids found under that label.
% With #modeb(1,same(var(node,any,x),var(node,any,x))):
%   pruned: :- same(V0,V1).
%   kept:   :- same(V0,V0).
:- mode_label_var(Section, Slot, Label, Left),
    mode_label_var(Section, Slot, Label, Right),
    Left != Right.

% CONSTRAINT. Within one literal, placeholders with different labels must hold
% different variables.
%   Section, Slot          the literal.
%   LeftLabel, RightLabel  two distinct labels; "<" lists each pair once.
%   Var                    the variable id found under both.
% With #modeb(1,edge(var(node,any,a),var(node,any,b))):
%   pruned: :- edge(V0,V0).
%   kept:   :- edge(V0,V1).
:- mode_label_var(Section, Slot, LeftLabel, Var),
    mode_label_var(Section, Slot, RightLabel, Var),
    LeftLabel < RightLabel.

% DEFINITION, local helper. mode_label_var(Section, Slot, Label, Var): inside
% the literal at that slot, a placeholder labelled Label holds Var.
%   Section, Slot  the selected literal, in head or body.
%   Label          source label of one of its placeholders.
%   Var            variable id written there.
% Used only by the last two constraints below.
mode_label_var(Section, Slot, Label, Var) :-
    selected(Section, Slot, Mode),
    mode_arg_label(Mode, Arg, Label),
    var_at(Section, Slot, Arg, Var).

% ----- legality/linkedness.lp -----

% CONSTRAINT. Every literal with clause-global variables must be linked to the
% root. It is a search policy, stricter than ASP safety.
%   Section, Slot  a literal with global variables.
%   pruned: q(V0) :- d(V0), r(V1).      r(V1) shares nothing with the rest
%   pruned: :- d(V0), r(V1,V2), s(V2).  {r,s} and {d} are two components
%   kept:   q(V0) :- d(V0), r(V0).
%   kept:   q(V0) :- d(V0), r(V0,V1), s(V1).   linked through a chain
:- variable_literal(Section, Slot), not linked_literal(Section, Slot).

% DEFINITION, local helper. linked_var(Var): Var is reachable from the root.
%   Var  clause-global variable id connected to the root literal through a
%        chain of literals sharing global variables.
% Used only in this file, in mutual recursion with linked_literal.
% Case 1: the variables of the root itself.
linked_var(Var) :-
    clause_root(Section, Slot),
    clause_var_at(Section, Slot, _, Var).

% DEFINITION, local helper. Same predicate. Case 2: a variable that shares a
% literal with an already linked variable.
%   Var    an already linked variable id.
%   Other  a variable id written in the same literal as Var.
linked_var(Other) :-
    linked_var(Var),
    clause_var_at(Section, Slot, _, Var),
    clause_var_at(Section, Slot, _, Other).

% DEFINITION, local helper. linked_var(Var), case 3: the variables of any
% linked literal. It closes the recursion for literals linked through case 3
% above, whose variables are not otherwise reachable.
linked_var(Var) :-
    linked_literal(Section, Slot),
    clause_var_at(Section, Slot, _, Var).

% DEFINITION, local helper. linked_literal(Section, Slot): the literal belongs
% to the root's connected component.
%   Section, Slot  the selected literal.
% Used by the constraint at the end of this file.
% Case 1: the root itself.
linked_literal(Section, Slot) :- clause_root(Section, Slot).

% DEFINITION, local helper. Same predicate. Case 2: a literal that mentions a
% linked variable.
linked_literal(Section, Slot) :-
    clause_var_at(Section, Slot, _, Var),
    linked_var(Var).

% DEFINITION, local helper. Same predicate. Case 3: every member of a selected
% choice, cardinality or aggregate head is linked as soon as one head literal
% is.
%   Slot  head slot of a member of the selected composite form.
% The head itself joins them: "{heads(V0);tails(V1)} :- coin(V0), coin(V1)."
% is one component although its elements share no variable.
linked_literal(head, Slot) :-
    selected_head_form(Form),
    composite_head_form(Form),
    head_form_member(Form, Slot, _),
    linked_literal(head, _).

% DEFINITION, local helper. clause_root(Section, Slot): the first literal with
% global variables, from which connectivity is propagated.
%   Section, Slot  the first head literal that has global variables, otherwise
%                  the first body literal that has them. Exactly one exists
%                  whenever any literal has a global variable.
% Used only in this file.
clause_root(Section, Slot) :-
    variable_literal(Section, Slot),
    not earlier_variable_literal(Section, Slot).

% DEFINITION, local helper. earlier_variable_literal(Section, Slot): some
% other literal with global variables precedes this one.
%   Section, Slot  a literal with global variables that is not the first.
% "Precedes" compares (section_order, Slot): head before body, then by slot.
% Used only to define clause_root below.
earlier_variable_literal(Section, Slot) :-
    variable_literal(Section, Slot),
    variable_literal(EarlierSection, EarlierSlot),
    section_order(Section, Order),
    section_order(EarlierSection, EarlierOrder),
    (EarlierOrder, EarlierSlot) < (Order, Slot).

% ----- representation/slots.lp -----

% DEFINITION, reusable fact. section_order(Section, Order): rank of a section.
%   Section  head.
%   Order    0: head literals come before every body literal.
% Shared with legality/linkedness.lp, which needs "head first" to pick the root
% literal. Clingo's own term order says body < head, the opposite.
section_order(head, 0).

% DEFINITION, reusable fact. Same predicate as above.
%   Section  body.
%   Order    1: body literals come after every head literal.
section_order(body, 1).

% ----- legality/linkedness.lp -----

% DEFINITION, local helper. variable_literal(Section, Slot): the literal at
% that slot has at least one clause-global variable.
%   Section, Slot  the selected literal.
% A literal without any, such as a ground atom or "#count{V0 : p(V0)} > 2",
% is exempt from linkedness. Used only in this file.
variable_literal(Section, Slot) :- clause_var_at(Section, Slot, _, _).

% Selected literals with global variables must form one connected component.
% Local names do not connect independent scopes. Elements of a selected choice
% head are connected by that head even when they use different variables.

% DEFINITION, local helper. clause_var_at(Section, Slot, Arg, Var): a
% clause-global occurrence of Var.
%   Section, Slot  the selected literal.
%   Arg            placeholder position inside it.
%   Var            variable id written there.
% It is var_at/4 without the placeholders that are local to an aggregate, a
% conditional or a choice element (local_var_at in legality/scopes.lp). Only
% such occurrences can connect two literals. Used only in this file.
clause_var_at(Section, Slot, Arg, Var) :-
    var_at(Section, Slot, Arg, Var),
    not local_var_at(Section, Slot, Arg).

% ----- legality/recall.lp -----

% CONSTRAINT. A condition declaration may not be attached more often than its
% recall.
%   Group   the condition declaration.
%   Count   its uses in the clause.
%   Recall  its cap (an unlimited recall is replaced by max_body).
% With #modec(1,node(var(node,any))):
%   pruned: :- p(V0) : node(V0); q(V1) : node(V1).    node attached twice
%   kept:   :- r(V0), p(V0) : node(V0).
:- selected_condition_group_count(Group, Count),
    condition_group_recall(Group, Recall),
    Count > Recall.

% Count uses of declarations, not just concrete mode variants.
% A shared recall group uses its tightest cap. Condition recalls are shared
% across every attachment in the clause, including head attachments.

% DEFINITION, local helper. selected_condition_group_count(Group, Count): how
% many times the clause attaches conditions of one condition declaration.
%   Group  id of a condition declaration (#modec) with a recall cap.
%   Count  total uses of that declaration over all selected modes, in head and
%          body. A mode that attaches it twice contributes 2.
% Used only by the constraint below.
selected_condition_group_count(Group, Count) :-
    condition_group_recall(Group, _),
    Count = #sum {
        Uses, Section, Slot, Mode :
        selected(Section, Slot, Mode),
        mode_condition_usage(Mode, Group, Uses)
    }.

% CONSTRAINT. A mode declaration may not be used more often than its recall.
%   Group   the declaration's recall group.
%   Count   its selected literals.
%   Recall  its cap.
% With #modeb(1,red(var(node,any))) and #modeb(2,edge(var(node,any),var(node,any))):
%   pruned: :- red(V0), red(V1), edge(V0,V1).        red used twice
%   kept:   :- red(V0), edge(V0,V1), edge(V1,V2).    edge twice is within 2
:- selected_count(Group, Count), group_recall(Group, Recall), Count > Recall.

% ----- legality/scopes.lp -----

% CONSTRAINT. Every local variable of a choice/aggregate head element must be
% bound inside that element.
%   Slot, Arg  a local placeholder of the head element.
%   Var        variable id written there.
%   pruned: {sel(V0) : not blocked(V0)}.     negation binds nothing
%   kept:   {sel(V0) : node(V0)}.
:- head_aggregate_local_at(head, Slot, Arg),
    var_at(head, Slot, Arg, Var),
    not local_condition_bound(head, Slot, head_aggregate, 0, Var).

% CONSTRAINT. Every local variable of a conditional literal must be bound by
% one of its own conditions.
%   Section, Slot  the conditional literal.
%   Var            a local variable id of it.
%   pruned: :- p(V0) : not q(V0).        no condition binds V0
%   pruned: h :- p(V0,V1) : q(V0).       V1 is local and unbound
%   kept:   :- p(V0) : q(V0).
:- conditional_local_var(Section, Slot, Var),
    not local_condition_bound(Section, Slot, conditional, -1, Var).

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

% ----- representation/conditionals.lp -----

% DEFINITION, reusable. conditional_positive_condition_var(Section, Slot,
% Condition, Var): a positive atom condition mentions Var.
%   Section, Slot  the selected conditional literal.
%   Condition      zero-based index of the condition inside that literal.
%   Var            variable id at a placeholder of that condition, which must
%                  be an atom without default negation.
% In "p(V0) : q(V0), not r(V1)" it holds for condition 0 and V0 only. Consumed
% by legality/scopes.lp: only such a condition can bind a local variable.
conditional_positive_condition_var(Section, Slot, Condition, Var) :-
    selected(Section, Slot, Mode),
    conditional_condition(Mode, Condition, _, positive),
    conditional_condition_arg(Mode, Condition, _, Arg),
    var_at(Section, Slot, Arg, Var).

% ----- legality/scopes.lp -----

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

% ----- representation/aggregates.lp -----

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

% ----- legality/scopes.lp -----

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

% CONSTRAINT. Every clause-global variable of a conditional literal must be
% ASP-safe; its own conditions do not ground it for the rest of the clause.
%   Section, Slot  the conditional literal.
%   Var            a clause-global variable id of it.
%   pruned: h(V0) :- p(V0,V1) : q(V1).          V0 is global via the head and
%                                               nothing grounds it
%   kept:   h(V0) :- d(V0), p(V0,V1) : q(V1).
:- conditional_global_var(Section, Slot, Var), not asp_safe(Var).

% ----- legality/asp_safety.lp -----

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

% DEFINITION, reusable. asp_safe(Var), case 3: a positive plain body atom
% grounds Var.
asp_safe(Var) :- normal_positive_body_var(Var).

% DEFINITION, reusable. asp_safe(Var), case 4: the result of an arithmetic
% literal whose operands are safe.
%   Slot  body slot of that literal.
%   Var   variable id of its result.
asp_safe(Var) :-
    arithmetic_result_safe(Slot),
    arithmetic_result(Slot, Var).

% ----- legality/flow/closure.lp -----

% DEFINITION, reusable. asp_safe(Var), the case missing from
% legality/asp_safety.lp: the output of a value-producing comparison whose
% other placeholders are all asp_safe.
%   Slot  body slot of that comparison.
%   Arg   a placeholder of it declared output.
%   Var   variable id written there; "d(V0), V1=V0+1" makes V1 safe.
asp_safe(Var) :-
    asp_ready_relation(Slot),
    selected(body, Slot, Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var).

% ----- legality/asp_safety.lp -----

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

% ----- legality/flow/closure.lp -----

% DEFINITION, local helper. asp_ready_relation(Slot): the same readiness test
% as ready_relation, but counting asp_safe variables instead of flow_bound
% ones.
%   Slot  body slot of a value-producing comparison whose every non-output
%         placeholder holds an asp_safe variable.
% The two notions differ: a head input is flow_bound without being asp_safe.
% Used only by the next rule.
asp_ready_relation(Slot) :-
    selected(body, Slot, Mode),
    relation_output_mode(Mode),
    relation_input_count(Mode, Count),
    Count <= #count {
        Arg, Var : mode_variable_arg(Mode, Arg),
                  not mode_arg_direction(Mode, Arg, output),
                  var_at(body, Slot, Arg, Var),
                  asp_safe(Var)
    }.

% ----- legality/flow/declarations.lp -----

% DEFINITION, reusable. relation_input_count(Mode, Count): how many
% placeholders a value-producing comparison must have bound first.
%   Mode   id of a comparison with at least one output (relation_output_mode),
%          such as "V2 = V0 + V1" declared with V2 as output.
%   Count  number of its variable placeholders that are not outputs.
% Consumed by legality/flow/closure.lp for both flow readiness and ASP
% readiness of the relation.
relation_input_count(Mode, Count) :-
    relation_output_mode(Mode),
    Count = #count {
        Arg : mode_variable_arg(Mode, Arg),
              not mode_arg_direction(Mode, Arg, output)
    }.

% ----- legality/scopes.lp -----

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

% ----- legality/typing.lp -----

% CONSTRAINT. Inside one literal, a variable may not sit at two placeholders
% of different declared types, unless the two are local to different elements
% of one aggregate.
%   Section, Slot  the literal.
%   A0 < A1        two of its placeholders holding the same variable Var.
%   Type0, Type1   their declared types.
% A placeholder declared "any" has no type and never conflicts. With
% #modeb(1,lives(var(person,any),var(city,any))):
%   pruned: :- lives(V0,V0).
%   kept:   :- lives(V0,V1).
%   kept:   :- #count{V0 : person(V0) ; V0 : city(V0)} = V1, n(V1).
%           each V0 is local to its own element
:- var_at(Section, Slot, A0, Var),
    var_at(Section, Slot, A1, Var),
    A0 < A1,
    not separate_aggregate_local_elements(Section, Slot, A0, A1),
    arg_type(Section, Slot, A0, Type0),
    arg_type(Section, Slot, A1, Type1),
    Type0 != Type1.

% Declared types are nominal and must agree inside each variable scope.
% Independent local aggregate/conditional scopes may reuse a variable name
% with different types; a global occurrence connects those positions.
%
% Two occurrences of one variable id denote the same variable unless both are
% local to different constructs. That gives two checks: inside one literal,
% and between a non-local occurrence and every other occurrence. They are
% stated per variable rather than per pair of placeholders, which would
% ground every pair of positions of the clause.

% DEFINITION, local helper. separate_aggregate_local_elements(body, Slot, A0,
% A1): two placeholders of one body aggregate are local to different elements.
%   body    the section; aggregates handled here occur only in the body.
%   Slot    body slot of the aggregate.
%   A0, A1  local placeholder positions owned by two different elements.
% In "#count{V0 : p(V0) ; V0 : q(V0)}" the two V0 are different variables.
% Used only, negated, by the constraint below.
separate_aggregate_local_elements(body, Slot, A0, A1) :-
    aggregate_element_arg(Slot, E0, A0), aggregate_element_arg(Slot, E1, A1),
    E0 != E1, local_var_at(body, Slot, A0), local_var_at(body, Slot, A1).

% CONSTRAINT. A variable with a non-local occurrence may not sit anywhere at
% a placeholder of a different declared type.
%   Var    the variable id.
%   Type0  a type declared at one of its non-local occurrences.
%   Type1  a different type declared at any of its occurrences.
% With #modeb(1,person(var(person,any))) and #modeb(1,city(var(city,any))):
%   pruned: :- person(V0), city(V0).      V0 would be both person and city
%   kept:   :- person(V0), city(V1).
%   kept:   :- #count{V0 : person(V0)} = V1, #count{V0 : city(V0)} = V1.
%           each V0 is local to its own aggregate, so the types do not meet
:- global_variable_type(Var, Type0),
    variable_type(Var, Type1),
    Type0 != Type1.

% DEFINITION, local helper. variable_type(Var, Type): some placeholder holding
% Var declares Type.
%   Var   variable id.
%   Type  nominal type declared at any of its occurrences, local or not.
% Used only by the last constraint.
variable_type(Var, Type) :-
    var_at(Section, Slot, Arg, Var),
    arg_type(Section, Slot, Arg, Type).

% DEFINITION, local helper. global_variable_type(Var, Type): a non-local
% placeholder holding Var declares Type.
%   Var   variable id with an occurrence outside local constructs.
%   Type  nominal type declared at such an occurrence.
% A non-local occurrence is the same variable as every other occurrence of
% the name, in any literal. Used only by the last constraint.
global_variable_type(Var, Type) :-
    var_at(Section, Slot, Arg, Var),
    not local_var_at(Section, Slot, Arg),
    arg_type(Section, Slot, Arg, Type).

% ----- legality/scopes.lp -----

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

% DEFINITION, reusable. local_var_at, case 2: local placeholders of
% choice/aggregate head elements.
local_var_at(head, Slot, Arg) :- head_aggregate_local_at(head, Slot, Arg).

% DEFINITION, reusable. local_var_at, case 3: local placeholders of
% conditional literals.
local_var_at(Section, Slot, Arg) :- conditional_local_at(Section, Slot, Arg).

% DEFINITION, reusable. head_aggregate_local_at(head, Slot, Arg): the
% placeholder inside a head element holds a local variable.
%   head, Slot  the head element.
%   Arg         placeholder position whose variable is not clause-global.
% Shared by the constraint below, local_var_at below and
% legality/asp_safety.lp (such a placeholder is not a global head variable).
head_aggregate_local_at(head, Slot, Arg) :-
    head_aggregate_element_position(head, Slot, Arg),
    var_at(head, Slot, Arg, Var), not global_context_var(Var).

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

% ----- symmetry/aggregates.lp -----

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

% DEFINITION, local helper. count_condition_orderable(Slot): the arguments of
% the condition of this #count may be put in canonical order.
%   Slot  body slot of a #count whose condition is full-local.
% Used only by the second constraint below.
count_condition_orderable(Slot) :-
    full_local_condition(Slot, Mode), count_aggregate_mode(Mode).

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

% DEFINITION, local helper. sum_condition_orderable(Slot, Weight): the
% arguments of the condition of this #sum may be ordered, except the weight.
%   Slot    body slot of a #sum whose condition is full-local.
%   Weight  variable id at tuple position 0, the summed term. It must keep its
%           place: exchanging it with another variable changes the sum.
% Used only by the third constraint below.
sum_condition_orderable(Slot, Weight) :-
    full_local_condition(Slot, Mode), sum_aggregate_mode(Mode),
    aggregate_tuple_binding(Slot, 0, Weight).

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

% ----- symmetry/arithmetic.lp -----

% CONSTRAINT. A commutative arithmetic literal writes its operands in
% ascending variable-id order.
%   Slot   body slot of the literal.
%   Left   variable id of the left operand.
%   Right  variable id of the right operand.
%   pruned: :- n(V0), n(V1), V1+V0=V2, r(V2).
%   kept:   :- n(V0), n(V1), V0+V1=V2, r(V2).
%   kept:   :- n(V0), V0+V0=V1, r(V1).          equal ids are not "greater"
:- selected(body,Slot,Mode),
   commutative_mode(Mode),
   arithmetic_operand(Slot,left,Left),
   arithmetic_operand(Slot,right,Right),
   Left > Right.

% Order operands only for modes whose types, directions and labels allow
% interchange. add_mode, mul_mode and abs_mode name the operator of every
% complete template; interchangeable_operands says its operands may swap.
%
% A commutative mode keeps only the ascending operand-id orientation:
%   kept:   V0+V1=V2    V0*V1=V2    |V0-V1|=V2    V0+V0=V1 (equal ids)
%   pruned: V1+V0=V2    V1*V0=V2    |V1-V0|=V2    (swapped copy of a kept one)
% Modes without a flag keep both orientations:
%   V0-V1=V2 and V1-V0=V2    operand order changes the value.
%   V0/V1=V2 and V1/V0=V2    div_mode is emitted but is not commutative.
%   var(numeric,input,a)+var(numeric,input,b)=...: both V0+V1=V2 and V1+V0=V2
%   survive because different labels make the operands non-interchangeable;
%   canonicalization merges them afterwards.

% DEFINITION, local helper. commutative_mode(Mode): swapping the two operands
% of this arithmetic template yields the same literal of the same template.
%   Mode  id of a complete arithmetic template whose operator is commutative
%         and whose operands have equal type, direction and label
%         (interchangeable_operands).
% Used only by the constraint below.
% Case 1: addition.
commutative_mode(Mode) :- add_mode(Mode), interchangeable_operands(Mode).
% DEFINITION, local helper. Same predicate. Case 2: multiplication.
commutative_mode(Mode) :- mul_mode(Mode), interchangeable_operands(Mode).
% DEFINITION, local helper. Same predicate. Case 3: absolute difference
% |Left-Right|.
commutative_mode(Mode) :- abs_mode(Mode), interchangeable_operands(Mode).

% ----- symmetry/comparisons.lp -----

% CONSTRAINT. A symmetric comparison with interchangeable operands writes them
% in ascending variable-id order.
%   Slot   body slot of the comparison.
%   Left   variable id at placeholder 0 (written on the left).
%   Right  variable id at placeholder 1 (written on the right).
%   pruned: :- p(V0), p(V1), V1 != V0.
%   kept:   :- p(V0), p(V1), V0 != V1.
% "<" and "<=" are untouched: V1 < V0 and V0 < V1 are different literals.
:- selected(body, Slot, Mode),
    symmetric_comparison(Mode),
    interchangeable_operands(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right),
    Left > Right.

% Choose the ascending variable-id orientation of a symmetric comparison whose
% operands may swap: X != Y and X = Y mean Y != X and Y = X. Operands with
% different types, directions or labels are not interchangeable: with
% b(V0), a(V1) and var(a)!=var(b), V1!=V0 is the only legal orientation.
%   kept:   V0!=V1   V0=V1        pruned: V1!=V0   V1=V0

% DEFINITION, local helper. symmetric_comparison(Mode): the operator of this
% simple binary comparison means the same in both directions.
%   Mode  id of a simple comparison template.
% Used only by the constraint below.
% Case 1: disequality.
symmetric_comparison(Mode) :- comparison_operator(Mode, neq).
% DEFINITION, local helper. Same predicate. Case 2: equality.
symmetric_comparison(Mode) :- comparison_operator(Mode, eq).

% ----- symmetry/conditions.lp -----

% CONSTRAINT. Conditions of the same variant inside one conditional literal
% appear in ascending order of their variable tuples; the order of conditions
% does not change the meaning.
%   Section, Slot  the conditional literal.
%   Left, Right    the two conditions found in descending order.
%   pruned: :- r(V0,V1,V2), p(V0) : q(V2), q(V1).
%   kept:   :- r(V0,V1,V2), p(V0) : q(V1), q(V2).
%   kept:   :- r(V0,V1,V2), p(V0) : q(V2), not q(V1).   different variants
% Conditions declared with different types are different variants as well:
% with e(X) : q(var(a)), q(var(b)) the two q cannot trade places, so
% ":- nb(V0); e(V1) : q(V1), q(V0)." is kept.
:- condition_tuple_gt(Section, Slot, Left, Right).

% Order conditions of the same template variant by their variable tuples.
% Variant identity preserves term shape and polarity.

% DEFINITION, local helper. condition_tuple_gt(Section, Slot, Left, Right):
% two interchangeable conditions of one conditional literal are written in
% descending order.
%   Section, Slot  the selected conditional literal.
%   Left           index of a condition.
%   Right          index of a later condition (Left < Right) of the same
%                  variant: same predicate, polarity, term shape and
%                  placeholder types, directions and labels.
% It holds when, at the first argument where the two conditions differ, the
% earlier one has the greater variable id. Relative is that argument: the
% #count requires every earlier argument (Previous < Relative) to hold equal
% variables in both conditions, which makes the comparison lexicographic.
% Used only by the constraint below.
condition_tuple_gt(Section, Slot, Left, Right) :-
    selected(Section, Slot, Mode),
    conditional_condition_variant(Mode, Left, Variant),
    conditional_condition_variant(Mode, Right, Variant),
    Left < Right,
    conditional_condition_arg(Mode, Left, Relative, LeftArg),
    conditional_condition_arg(Mode, Right, Relative, RightArg),
    var_at(Section, Slot, LeftArg, LeftVar),
    var_at(Section, Slot, RightArg, RightVar),
    LeftVar > RightVar,
    Relative = #count {
        Previous :
        conditional_condition_arg(Mode, Left, Previous, PreviousLeftArg),
        conditional_condition_arg(Mode, Right, Previous, PreviousRightArg),
        Previous < Relative,
        var_at(Section, Slot, PreviousLeftArg, PreviousVar),
        var_at(Section, Slot, PreviousRightArg, PreviousVar)
    }.

% ----- symmetry/slots.lp -----

% Choose one slot encoding: no gaps, nondecreasing modes, sorted equal-mode tuples.
% Equal modes are contiguous; adjacent tuple checks therefore suffice.
% The decoder and duplicate checks rely on these ordering invariants.

% CONSTRAINT. Slots are filled from 0 upwards without gaps.
%   Section  head or body.
%   Slot     an occupied slot above 0 whose predecessor is empty.
% The same two-literal body could otherwise sit in slots {0,1}, {0,2}, {1,2}...
%   pruned: selected(body,1,M) with no selected(body,0,_)
%   kept:   selected(body,0,M), selected(body,1,N)
:- selected_slot(Section, Slot), Slot > 0, not selected_slot(Section, Slot-1).

% CONSTRAINT. Within a section, mode ids never decrease along the slots. It
% fixes the order of literals of different modes and makes equal modes
% contiguous.
%   Section       head or body.
%   Slot0, Slot1  two consecutive occupied slots. Slots have no gaps (see
%                 above), so checking neighbours orders the whole section.
%   Mode0, Mode1  their mode ids.
% With mode 4 = edge/2 and mode 7 = red/1:
%   pruned: selected(body,0,7), selected(body,1,4)     red(..), edge(..)
%   kept:   selected(body,0,4), selected(body,1,7)     edge(..), red(..)
:- selected(Section, Slot0, Mode0), selected(Section, Slot1, Mode1), Slot1 = Slot0 + 1, Mode0 > Mode1.

% CONSTRAINT. Adjacent literals of the same mode appear in ascending order of
% their variable tuples. Identical tuples pass here and are rejected as
% duplicates by pruning/redundancy/literals.lp.
%   Section, Slot0, Slot1  the adjacent pair found in descending order.
%   pruned: :- edge(V0,V2), edge(V0,V1).      (0,2) before (0,1)
%   kept:   :- edge(V0,V1), edge(V0,V2).
:- same_mode_tuple_gt(Section, Slot0, Slot1).

% DEFINITION, local helper. same_mode_tuple_gt(Section, Slot0, Slot1): two
% adjacent literals of the same mode are written in descending order.
%   Section  head or body.
%   Slot0    a slot.
%   Slot1    the next slot (Slot0 + 1), holding the same mode.
% It holds when, at the first placeholder where the two literals differ, the
% earlier literal has the greater variable id. Arg is that placeholder: the
% two #count aggregates state that every earlier placeholder (Prev < Arg)
% holds equal variables in both, which makes the comparison lexicographic.
% Used only by the constraint below.
same_mode_tuple_gt(Section, Slot0, Slot1) :-
    selected(Section, Slot0, Mode),
    selected(Section, Slot1, Mode),
    Slot1 = Slot0 + 1,
    mode_variable_arg(Mode, Arg),
    var_at(Section, Slot0, Arg, Left),
    var_at(Section, Slot1, Arg, Right),
    Left > Right,
    Before = #count{Prev : mode_variable_arg(Mode, Prev), Prev < Arg},
    Before = #count{
        Prev : mode_variable_arg(Mode, Prev), Prev < Arg,
        var_at(Section, Slot0, Prev, Same),
        var_at(Section, Slot1, Prev, Same)
    }.

% ----- symmetry/variables.lp -----

% CONSTRAINT. Variable ids are used without gaps, starting at 0.
%   Var1  a used variable id.
%   Var0  a smaller id of the domain that is not used.
%   pruned: :- edge(V0,V2).      V1 is skipped
%   kept:   :- edge(V0,V1).
:- used_var(Var1), var(Var0), Var0 < Var1, not used_var(Var0).

% CONSTRAINT. Ids grow in the order of first occurrence: a smaller id never
% first occurs after a greater one. Renaming variables does not change a
% clause, so one naming per clause is kept.
%   Var0, Var1            two consecutive used ids. Ids have no gaps (see
%                         above), so ordering neighbours orders them all.
%   (S0,L0,A0), (S1,L1,A1)  their first positions.
%   pruned: :- edge(V1,V0).                   V1 occurs before V0
%   kept:   :- edge(V0,V1).
%   kept:   target(V1,V0) :- edge(V0,V1).     the body is read first, so the
%                                             head may list ids in any order
:- first_var_pos(Var0, S0, L0, A0),
    first_var_pos(Var1, S1, L1, A1),
    Var1 = Var0 + 1,
    (S0, L0, A0) > (S1, L1, A1).

% DEFINITION, local helper. first_var_pos(Var, Section, Slot, Arg): where Var
% first occurs.
%   Var      a used variable id.
%   Section  section of its first occurrence.
%   Slot     slot of its first occurrence.
%   Arg      placeholder position of its first occurrence.
% "First" is the minimum of (Section, Slot, Arg) in Clingo's term order, in
% which body < head: a body occurrence precedes every head occurrence. Used
% only by the constraint below.
first_var_pos(Var, Section, Slot, Arg) :-
    used_var(Var),
    (Section, Slot, Arg) = #min{(S, L, A) : var_at(S, L, A, Var)}.

% ----- pruning/contradictions/comparisons.lp -----

% Reject strict self comparisons and strict/non-strict reverse pairs.
% Strict/strict reverse pairs are covered by the cycle check in numeric.lp.

% CONSTRAINT. A strict comparison between a variable and itself can never
% hold, so the body is unsatisfiable.
%   Slot               body slot of a comparison outside the positive simple
%                      case already covered by pruning/policies/comparisons.lp.
%   LeftArg, RightArg  placeholders of two adjacent plain variables related by
%                      "<" or ">" (strict_comparison_args).
%   Var                the single variable id written at both.
%   pruned: :- p(V0), V0 < V0 < 3.
%   pruned: :- p(V0), p(V1), V0 <= V1 < V1.    one strict link of a chain
%   kept:   :- p(V0), p(V1), V0 < V1.
:- selected(body, Slot, Mode),
    strict_comparison_args(Mode, LeftArg, RightArg),
    var_at(body, Slot, LeftArg, Var),
    var_at(body, Slot, RightArg, Var).

% CONSTRAINT. "Left < Right" together with "Right <= Left" can never hold.
%   Left, Right  variable ids.
%   pruned: :- p(V0,V1), V0 < V1, V1 <= V0.
%   pruned: :- p(V0,V1), V0 < V1, V0 >= V1.    ">=" is read as V1 <= V0
%   kept:   :- p(V0,V1), V0 < V1.
:- selected_lt(Left, Right), selected_leq(Right, Left).

% CONSTRAINT. Equal numeric values cannot satisfy a strict comparison.
% All selected builtins must be simple numeric comparisons: otherwise the
% existing Python fallback can retain this raw form. This moves only models
% that linear normalization already discards, before decode and construction.
%   Left, Right  equality variable ids.
%   pruned: p(V0), V0=V1, V1=V2, V0<V2.
%   kept:   p(V0,V1), V0=V1, V0<=V1.
:- not complex_numeric_builtin_selected,
   anchored_numeric_equality(Left), numeric_equality_path(Left, Right),
   selected_lt(Left, Right).
% CONSTRAINT. Equal numeric values cannot satisfy a disequality.
%   Left, Right  equality variable ids.
%   pruned: p(V0), V0=V1, V1=V2, V0!=V2.
%   kept:   V0=0, V0!=0.                 no simple, anchored equality
:- not complex_numeric_builtin_selected,
   anchored_numeric_equality(Left), numeric_equality_path(Left, Right),
   selected_neq(Left, Right).

% DEFINITION, local helper. complex_numeric_builtin_selected: the selected
% body contains a builtin outside simple numeric comparisons. Its component
% may use an expression or structural fallback instead of linear normalization.
% Used only as a guard by the two constraints below; declarations that are
% not selected do not block the simple case.
complex_numeric_builtin_selected :-
    selected(body, _, Mode), complex_numeric_builtin_mode(Mode).

% DEFINITION, local helper. anchored_numeric_equality(Var): Var's equality
% component has an external variable grounded by a positive plain body atom.
% This makes linear normalization applicable; components without an external
% variable retain their structural fallback.
anchored_numeric_equality(Var) :-
    numeric_equality_path(Var, Anchor), normal_positive_body_var(Anchor).

% DEFINITION, local helper. numeric_equality_path(Left, Right): selected simple
% numeric equalities connect these variables, so their values must be equal.
% Case 1: a selected equality; case 2: extend through another selected equality.
% This closure uses variable ids without products of arithmetic coefficients.
numeric_equality_path(Left, Right) :- numeric_equality(Left, Right).
numeric_equality_path(Left, Right) :-
    numeric_equality_path(Left, Middle), numeric_equality(Middle, Right).

% DEFINITION, local helper. numeric_equality(Left, Right): a selected simple
% positive numeric equality between distinct variable ids. The symmetric view
% describes equal values; it never swaps bindings of the selected template.
% Used only by numeric_equality_path below.
numeric_equality(Left, Right) :-
    selected(body, Slot, Mode), numeric_equality_mode(Mode),
    var_at(body, Slot, 0, Left), var_at(body, Slot, 1, Right), Left != Right.
% DEFINITION, local helper. Same predicate, symmetric value equality.
numeric_equality(Right, Left) :- numeric_equality(Left, Right).

% CONSTRAINT. A homogeneous equality cannot coexist with its proportional
% strict comparison or disequality. This moves only normalization rejections:
%   pruned: p(V0), 2*V0=V1, 4*V0<2*V1.
%   pruned: p(V0), 2*V0=V0, 4*V0<2*V0.           nonzero collapsed row
%   kept:   p(V0), 2*V0=V1, 4*V0<2*V1, V0*V0=V1.   expression fallback
%   kept:   V0-V0=0, V0-V0!=0.                     structural fallback
% Coefficients are normalized statically in Python, never multiplied in ASP.
:- linear_conflict_slots(Equality, Comparison),
   not nonlinear_builtin_selected,
   not linear_conflict_bindings_differ(Equality, Comparison),
   not linear_conflict_repeated_binding(Equality),
   linear_conflict_anchored(Equality).

% DEFINITION, local helper. Selected builtins outside homogeneous numeric
% linear rows retain the expression/structural fallback of the whole component.
nonlinear_builtin_selected :- selected(body, _, Mode), nonlinear_builtin_mode(Mode).

% DEFINITION, local helper. The paired rows disagree at some ordered binding.
% Every placeholder has one binding, and the paired rows have equal arity.
linear_conflict_bindings_differ(Equality, Comparison) :-
    linear_conflict_slots(Equality, Comparison),
    var_at(body, Equality, Arg, Var), not var_at(body, Comparison, Arg, Var).

% DEFINITION, local helper. A statically proved pair of proportional templates
% is selected. Project slots before comparing their complete variable bindings.
linear_conflict_slots(Equality, Comparison) :-
    numeric_linear_conflict(EqualityMode, ComparisonMode),
    selected(body, Equality, EqualityMode), selected(body, Comparison, ComparisonMode).

% DEFINITION, local helper. Repeated bindings can cancel the anchored column;
% leave these cases to Python. With at most two nonzero columns and nonzero
% coefficient sum, the compiler proves that aliasing cannot erase the anchor.
linear_conflict_repeated_binding(Equality) :-
    numeric_linear_distinct_mode(Mode), selected(body, Equality, Mode),
    var_at(body, Equality, First, Var), var_at(body, Equality, Second, Var), First < Second.

% DEFINITION, local helper. Nonzero coefficients and the guarded aliasing cases
% ensure that this positive plain body anchor belongs to the actual equality row.
linear_conflict_anchored(Equality) :-
    numeric_linear_conflict(Mode, _), selected(body, Equality, Mode),
    var_at(body, Equality, _, Anchor), normal_positive_body_var(Anchor).

% ----- pruning/contradictions/numeric.lp -----

% Reject impossible arithmetic/order combinations under the per-argument sign
% evidence of inference/numeric.lp. Inferred strict-order cycles are impossible.
% Each rule requires the sign of exactly the operand that makes it impossible:
%   R = L + Rt, R < L   needs Rt >= 0 (R = A - B can be negative otherwise)
%   R = L \ D, D <= R   needs D > 0
%   R = L * Rt, R < L   needs L > 0 and Rt > 0
%   R = L / Rt, L < R   needs L >= 0 and Rt > 0
%
% In the examples below n/1 is a closed predicate whose argument is proved
% > 0 (positive_arg) and z/1 one whose argument is proved >= 0
% (nonnegative_arg); "..." stands for the rest of an otherwise legal clause.

% This cycle check also covers opposite selected strict comparisons and
% strict reversals of the operand/result order inferred from positive addition.
% CONSTRAINT. The entailed strict order may not contain a cycle: no variable
% can be strictly below itself.
%   Var  a variable id on a cycle of inferred_lt.
%   pruned: ..., V0 < V1, V1 < V0.                  opposite comparisons
%   pruned: ..., V0 < V1, V1 < V2, V2 < V0.         a longer cycle
%   pruned: n(V1), V0+V1=V2, V2 < V0.               V0 < V2 is inferred
%   kept:   ..., V0 < V1, V1 < V2.
:- inferred_lt(Var, Var).

% ----- inference/numeric.lp -----

% DEFINITION, reusable. inferred_lt(Left, Right): the clause entails that the
% value of Left is strictly below the value of Right.
%   Left   variable id of the smaller value.
%   Right  variable id of the greater value.
% Unlike selected_lt/2 it includes consequences nobody wrote as a literal.
% Consumed by pruning/contradictions/numeric.lp, which rejects a cycle.
% Case 1: every explicit strict comparison.
inferred_lt(Left, Right) :- selected_lt(Left, Right).

% DEFINITION, reusable. Same predicate. Case 2: in Left + Right = Result with
% Right > 0, Left is below Result.
%   Slot    body slot of the addition.
%   Left    left operand, the smaller value.
%   Right   right operand, already positive.
%   Result  the sum, the greater value.
inferred_lt(Left, Result) :-
    addition(Slot, Left, Right, Result),
    positive_value(Right).

% DEFINITION, reusable. Same predicate. Case 3: the mirror image; with
% Left > 0, Right is below Result.
inferred_lt(Right, Result) :-
    addition(Slot, Left, Right, Result),
    positive_value(Left).

% DEFINITION, reusable. Same predicate. Case 4: transitive closure.
%   Left, Middle, Right  variable ids with Left < Middle and Middle < Right.
inferred_lt(Left, Right) :- inferred_lt(Left, Middle), inferred_lt(Middle, Right).

% ----- pruning/contradictions/numeric.lp -----

% CONSTRAINT. With Right >= 0, the sum Left + Right cannot be below Left.
%   Slot    body slot of "Left + Right = Result".
%   Left    left operand.
%   Right   right operand, proved >= 0.
%   Result  the sum, explicitly compared as Result < Left.
%   pruned: z(V1), V0+V1=V2, V2 < V0.
%   kept:   V0+V1=V2, V2 < V0 without sign evidence for V1 (V1 may be negative)
:- addition(Slot, Left, Right, Result),
    nonnegative_value(Right),
    selected_lt(Result, Left).

% CONSTRAINT. The mirror image: with Left >= 0, the sum cannot be below Right.
%   Left    left operand, proved >= 0.
%   Right   right operand.
%   Result  the sum, explicitly compared as Result < Right.
%   pruned: z(V0), V0+V1=V2, V2 < V1.
%   kept:   V0+V1=V2, V2 < V1 without sign evidence for V0
:- addition(Slot, Left, Right, Result),
    nonnegative_value(Left),
    selected_lt(Result, Right).

% CONSTRAINT. With Right > 0, the sum Left + Right cannot be below or equal
% to Left.
%   Right   right operand, proved > 0.
%   Result  the sum, explicitly compared as Result <= Left.
%   pruned: n(V1), V0+V1=V2, V2 <= V0.
%   kept:   z(V1), V0+V1=V2, V2 <= V0.      V1 = 0 makes V2 = V0 possible
:- addition(Slot, Left, Right, Result),
    positive_value(Right),
    selected_leq(Result, Left).

% CONSTRAINT. The mirror image: with Left > 0, the sum cannot be below or
% equal to Right.
%   Left    left operand, proved > 0.
%   Result  the sum, explicitly compared as Result <= Right.
%   pruned: n(V0), V0+V1=V2, V2 <= V1.
%   kept:   z(V0), V0+V1=V2, V2 <= V1.
:- addition(Slot, Left, Right, Result),
    positive_value(Left),
    selected_leq(Result, Right).

% CONSTRAINT. A remainder is always below a positive divisor, so
% "Divisor <= Result" is impossible.
%   Slot     body slot of "Dividend \ Divisor = Result".
%   Divisor  right operand, proved > 0.
%   Result   the remainder, explicitly compared as Divisor <= Result.
%   pruned: n(V1), V0\V1=V2, V1 <= V2.
%   kept:   n(V1), V0\V1=V2, V2 < V1.
:- modulo(Slot, _, Divisor, Result),
    positive_value(Divisor),
    selected_leq(Divisor, Result).

% ----- representation/arithmetic.lp -----

% DEFINITION, reusable. modulo(Slot, Left, Right, Result): the body states
% Left \ Right = Result.
%   Slot    body slot of the literal.
%   Left    variable id of the dividend.
%   Right   variable id of the divisor.
%   Result  variable id of the remainder.
% Operand order matters. Consumed by pruning/contradictions/numeric.lp.
modulo(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), mod_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).

% ----- pruning/contradictions/numeric.lp -----

% CONSTRAINT. A product of two positive integers cannot be below its left
% factor.
%   Left, Right  factors, both proved > 0.
%   Result       the product, explicitly compared as Result < Left.
%   pruned: n(V0), n(V1), V0*V1=V2, V2 < V0.
%   kept:   n(V0), n(V1), V0*V1=V2, V2 <= V0.    equal when V1 = 1
:- multiplication(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right),
    selected_lt(Result, Left).

% CONSTRAINT. The mirror image: the product cannot be below its right factor.
%   Result  the product, explicitly compared as Result < Right.
%   pruned: n(V0), n(V1), V0*V1=V2, V2 < V1.
%   kept:   n(V0), n(V1), V0*V1=V2, V2 <= V1.
:- multiplication(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right),
    selected_lt(Result, Right).

% CONSTRAINT. Dividing a value >= 0 by a positive integer cannot yield more
% than the value.
%   Left    dividend, proved >= 0.
%   Right   divisor, proved > 0.
%   Result  the quotient, explicitly compared as Left < Result.
%   pruned: z(V0), n(V1), V0/V1=V2, V0 < V2.
%   kept:   z(V0), n(V1), V0/V1=V2, V2 <= V0.
:- division(Slot, Left, Right, Result),
    nonnegative_value(Left),
    positive_value(Right),
    selected_lt(Left, Result).

% ----- representation/arithmetic.lp -----

% DEFINITION, reusable. division(Slot, Left, Right, Result): the body states
% Left / Right = Result (integer division).
%   Slot    body slot of the literal.
%   Left    variable id of the dividend.
%   Right   variable id of the divisor.
%   Result  variable id of the quotient.
% Operand order matters. Consumed by pruning/contradictions/numeric.lp.
division(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), div_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).

% ----- pruning/policies/aggregates.lp -----

% Existing aggregate restrictions: distinct tuple and condition bindings,
% plus a result used outside the aggregate. These are restrictions of
% the enumerator; ASP itself also permits aggregates outside this subset.

% CONSTRAINT (policy). One variable may not fill two tuple positions of an
% aggregate.
%   Slot           body slot of an aggregate of the single-element subset.
%   First, Second  two different tuple positions.
%   Variable       the variable id written at both.
%   pruned: #count{V0,V0 : p(V0,V1)} = V2
%   kept:   #count{V0,V1 : p(V0,V1)} = V2
:- aggregate_tuple_binding(Slot, First, Variable),
    aggregate_tuple_binding(Slot, Second, Variable), First < Second.

% CONSTRAINT (policy). One variable may not fill two condition placeholders
% of an aggregate, whether in the same condition or in two conditions. The
% second case means this subset never joins two conditions on a variable.
%   Slot           body slot of an aggregate of the single-element subset.
%   First, Second  two different flattened condition positions.
%   Variable       the variable id written at both.
%   pruned: #count{V0 : p(V0,V0)} = V1
%   pruned: #count{V0 : p(V0), q(V0)} = V1      a join of p and q on V0
%   kept:   #count{V0 : p(V0), q(V1)} = V2
:- aggregate_condition_position(Slot, First, Variable),
    aggregate_condition_position(Slot, Second, Variable), First < Second.

% CONSTRAINT (policy). The result of an aggregate must be used elsewhere in
% the clause: in the head or in another body literal.
%   Slot      body slot of an aggregate of the single-element subset.
%   Variable  variable id of its result.
%   pruned: h(V0) :- d(V0), #count{V1 : p(V1)} = V2.     V2 is never read
%   kept:   h(V2) :- #count{V1 : p(V1)} = V2.
:- aggregate_result_var(Slot, Variable), not var_used_outside_body_slot(Slot, Variable).

% CONSTRAINT (policy). The same requirement for the equality output of any
% body aggregate.
%   Slot      body slot of an aggregate.
%   Variable  variable id of its equality output.
%   pruned: h(V0) :- d(V0), #sum{V1 : p(V1) ; V2 : q(V2)} = V3.   V3 is never read
%   kept:   h(V3) :- #sum{V1 : p(V1) ; V2 : q(V2)} = V3.
:- aggregate_output_var(Slot, Variable), not var_used_outside_body_slot(Slot, Variable).

% ----- representation/aggregates.lp -----

% DEFINITION, reusable. aggregate_output_var(Slot, Variable): a variable the
% aggregate at body Slot assigns through an equality guard.
%   Slot      body slot of an aggregate.
%   Variable  variable id at an output guard: V1 in "#sum{...} = V1".
% Shared by legality/asp_safety.lp and legality/flow/seeds.lp (an output is
% safe and produced) and pruning/policies/aggregates.lp (it must be used).
aggregate_output_var(Slot, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_output_arg(Mode, Position),
    var_at(body, Slot, Position, Variable).

% ----- pruning/policies/comparisons.lp -----

% Exclude self comparisons and opposite non-strict edges.
% The latter force equal values, not identical variable ids; this preserves the
% existing variable-identification policy rather than asserting inconsistency.

% CONSTRAINT (policy). A simple binary comparison may not compare a variable
% with itself: it is either always true (=, <=, >=) or never true (!=, <, >).
%   Slot  body slot of a simple binary comparison, whatever its operator.
%   Var   the single variable id written at both placeholders 0 and 1.
%   pruned: :- p(V0), V0 <= V0.
%   pruned: :- p(V0), V0 != V0.
%   kept:   :- p(V0), p(V1), V0 <= V1.
:- selected(body, Slot, Mode),
    comparison_operator(Mode, _),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var).

% CONSTRAINT (policy). "Left <= Right" together with "Right <= Left" is not
% generated. The pair is satisfiable (it forces equal values), so this is not
% a contradiction: the enumerator expresses equality by writing one variable
% id instead.
%   Left, Right  variable ids.
%   pruned: h(V0) :- p(V0,V1), V0 <= V1, V1 <= V0.
%   kept:   h(V0) :- p(V0,V0).                        the same meaning
:- selected_leq(Left, Right), selected_leq(Right, Left).

% ----- pruning/policies/singletons.lp -----

% Retain the existing singleton policy. Positive existential projections and
% local aggregate/conditional names are exempt. This is a search-space policy,
% not a general theorem that ASP variables must occur twice.

% CONSTRAINT (policy). A variable that occurs exactly once must be an
% existential projection: written in a positive plain body atom, or local to
% an aggregate or a conditional literal.
%   Var  a used variable id with a single occurrence that has none of those
%        three exemptions.
%   pruned: h(V0) :- p(V0), not q(V0,V1).    V1 occurs once, under negation
%   pruned: h(V0,V1) :- p(V0).               V1 occurs once, in the head
%   kept:   h(V0) :- p(V0,V1).               V1 occurs once in a positive atom
%   kept:   h(V0) :- p(V0), #count{V1 : q(V1,V2)} = V0.   V2 is local
:- used_var(Var),
    not repeated_var(Var),
    not normal_positive_body_var(Var),
    not aggregate_local_var(_, Var),
    not conditional_local_var(_, _, Var).

% ----- representation/variables.lp -----

% DEFINITION, reusable. repeated_var(Var): Var occurs at two or more places.
%   Var  variable id held by two different placeholders. A placeholder is a
%        triple (Section, Slot, Position); the two may be in the same literal,
%        as in p(V0,V0), or in different literals.
% Consumed by pruning/policies/singletons.lp, where "not repeated" means
% singleton. Kept here because it states a fact about occurrences, not a policy.
% Counting the placeholders grounds one rule per variable; comparing them
% pairwise would ground one per pair of placeholders.
repeated_var(Var) :-
    used_var(Var),
    2 <= #count { Section, Slot, Arg : var_at(Section, Slot, Arg, Var) }.

% DEFINITION, reusable. aggregate_local_var(Slot, Var): Var plays only the
% condition role inside the aggregate at body Slot.
%   Slot  body slot holding an aggregate of the single-element equality subset.
%   Var   variable id that occurs in a condition of that aggregate and is
%         neither one of its tuple terms nor its result.
% In "#count{V0 : p(V0,V1)} = V2" this holds for V1 only. It classifies by
% role, not by scope: whether V1 is clause-global is decided in
% legality/scopes.lp. Consumed by pruning/policies/singletons.lp to exempt
% such names from the singleton policy.
aggregate_local_var(Slot, Var) :-
    aggregate_condition_var(Slot, Var),
    not aggregate_tuple_var(Slot, Var),
    not aggregate_result_var(Slot, Var).

% ----- representation/aggregates.lp -----

% DEFINITION, reusable. aggregate_condition_var(Slot, Variable): Variable
% occurs in some condition of the aggregate at body Slot.
%   Slot      body slot of an aggregate of the single-element subset.
%   Variable  variable id at any condition placeholder.
% Shared by representation/variables.lp and legality/aggregates.lp.
aggregate_condition_var(Slot, Variable) :- aggregate_condition_position(Slot, _, Variable).

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

% ----- legality/scopes.lp -----

% DEFINITION, reusable. conditional_local_var(Section, Slot, Var): Var is
% local to the conditional literal at that slot.
%   Section, Slot  the selected conditional literal.
%   Var            variable id of it that is not clause-global.
% Shared by this file and pruning/policies/singletons.lp, which exempts local
% names.
conditional_local_var(Section, Slot, Var) :-
    conditional_var(Section, Slot, Var),
    not global_context_var(Var).

% ----- representation/conditionals.lp -----

% DEFINITION, reusable. conditional_var(Section, Slot, Var): Var occurs
% anywhere in the conditional literal at that slot.
%   Section, Slot  the selected conditional literal.
%   Var            variable id of its conclusion or of any condition.
% Consumed by legality/scopes.lp, which splits these variables into local and
% global.
% Case 1: conclusion variables.
conditional_var(Section, Slot, Var) :- conditional_main_var(Section, Slot, Var).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: condition variables.
conditional_var(Section, Slot, Var) :- conditional_condition_var(Section, Slot, Var).

% DEFINITION, local helper. conditional_main_var(Section, Slot, Var): Var is
% written in the conclusion of the conditional literal at that slot.
%   Section, Slot  the selected conditional literal.
%   Var            variable id at a conclusion placeholder. In
%                  "p(V0,V1) : q(V1)" these are V0 and V1.
% Used only by conditional_var below.
conditional_main_var(Section, Slot, Var) :-
    selected(Section, Slot, Mode),
    conditional_main_arg(Mode, Arg),
    var_at(Section, Slot, Arg, Var).

% DEFINITION, local helper. conditional_condition_var(Section, Slot, Var): Var
% is written in some condition of the conditional literal at that slot.
%   Section, Slot  the selected conditional literal.
%   Var            variable id at a placeholder of any condition, whatever its
%                  polarity or kind. In "p(V0,V1) : q(V1), not r(V2)" these are
%                  V1 and V2.
% Used only by conditional_var below.
conditional_condition_var(Section, Slot, Var) :-
    selected(Section, Slot, Mode),
    conditional_condition_arg(Mode, _, _, Arg),
    var_at(Section, Slot, Arg, Var).

% ----- legality/scopes.lp -----

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

% ----- representation/aggregates.lp -----

% DEFINITION, reusable. aggregate_internal_position(body, Slot, Position): the
% same fact with its section made explicit.
%   body      the section; aggregates handled here occur only in the body.
%   Slot      body slot of an aggregate.
%   Position  flattened interior placeholder position.
% Consumed by legality/scopes.lp, whose global_context_var rule ranges over
% both sections and therefore needs a Section argument to negate against.
aggregate_internal_position(body, Slot, Position) :- aggregate_internal_arg(Slot, Position).

% ----- legality/scopes.lp -----

% DEFINITION, local helper. head_aggregate_element_position(head, Slot, Arg):
% the placeholder lies inside a choice/aggregate head element.
%   head  the section; such elements occur only in the head.
%   Slot  head slot of the element.
%   Arg   placeholder position of its tuple, its atom or one of its
%         conditions; never a guard.
% Used by global_context_var above and head_aggregate_local_at below.
head_aggregate_element_position(head, Slot, Arg) :-
    selected(head, Slot, Mode), head_aggregate_element_arg(Mode, Arg).

% ----- pruning/properties/acyclic.lp -----

% CONSTRAINT. Three positive atoms of an acyclic predicate may not form a
% triangle: the body could never be satisfied.
%   Slot0 < Slot1 < Slot2  body slots of the three atoms.
%   Pred                   the acyclic binary predicate.
%   X, Y, Z                variable ids with X->Y, Y->Z and Z->X.
% With before/2 acyclic:
%   pruned: :- before(V0,V1), before(V1,V2), before(V2,V0).
%   kept:   :- before(V0,V1), before(V1,V2).
:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    positive_body_literal(Slot2, _, Pred, 2),
    Slot0 < Slot1,
    Slot1 < Slot2,
    positive_body_capacity(Pred, Capacity), Capacity >= 3,
    acyclic_pred(Pred),
    var_at(body, Slot0, 0, X),
    var_at(body, Slot0, 1, Y),
    var_at(body, Slot1, 0, Y),
    var_at(body, Slot1, 1, Z),
    var_at(body, Slot2, 0, Z),
    var_at(body, Slot2, 1, X).

% CONSTRAINT. After a positive two-step path X->Y->Z of an acyclic predicate,
% the negated back-edge "not Pred(Z,X)" is always true and therefore
% redundant.
%   Slot0, Slot1  body slots of the two positive atoms of the path.
%   Slot2         body slot of the negated atom.
%   X, Y, Z       variable ids of the path.
% With before/2 acyclic:
%   pruned: :- before(V0,V1), before(V1,V2), not before(V2,V0).
%   kept:   :- before(V0,V1), before(V1,V2), not before(V0,V2).   not a back-edge
:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    negative_body_literal(Slot2, _, Pred, 2),
    acyclic_pred(Pred),
    var_at(body, Slot0, 0, X),
    var_at(body, Slot0, 1, Y),
    var_at(body, Slot1, 0, Y),
    var_at(body, Slot1, 1, Z),
    var_at(body, Slot2, 0, Z),
    var_at(body, Slot2, 1, X).

% ----- pruning/properties/antisymmetric.lp -----

% Closed-world antisymmetric predicate property.
%
% This file owns only antisymmetric pruning: reject two positive body literals
% Pred(X, Y) and Pred(Y, X) for distinct variable ids. Antisymmetry forces equal
% values; this is variable-identification pruning, not proof of unequal values.
% Stronger properties such as asymmetric,
% acyclic, strict_order, and total_order derive antisymmetric_pred(Pred) in
% their own files.

% CONSTRAINT. An antisymmetric predicate may not be written in both directions
% over two different variable ids. The pair is satisfiable only when both
% values are equal, which the enumerator expresses by writing one id.
%   Slot0 < Slot1  body slots of the two positive atoms.
%   Pred           the antisymmetric binary predicate.
%   Left, Right    two different variable ids: Pred(Left,Right) at Slot0 and
%                  Pred(Right,Left) at Slot1.
% With le/2 antisymmetric:
%   pruned: h(V0) :- le(V0,V1), le(V1,V0).
%   kept:   h(V0) :- le(V0,V0).               the same meaning with one id
%   kept:   h(V0) :- le(V0,V1), le(V1,V2).
:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    Slot0 < Slot1,
    antisymmetric_pred(Pred),
    var_at(body, Slot0, 0, Left),
    var_at(body, Slot0, 1, Right),
    Left != Right,
    var_at(body, Slot1, 0, Right),
    var_at(body, Slot1, 1, Left).

% ----- pruning/properties/acyclic.lp -----

% DEFINITION, reusable property bridge. antisymmetric_pred(Pred): Pred never
% holds in both directions for two different values.
%   Pred  signed predicate id of a binary closed predicate proved acyclic.
% An acyclic relation has no cycle of length 2. The reversed-pair check is
% owned by pruning/properties/antisymmetric.lp.
antisymmetric_pred(Pred) :- acyclic_pred(Pred).

% ----- pruning/properties/asymmetric.lp -----

% DEFINITION, reusable property bridge. antisymmetric_pred(Pred): Pred never
% holds in both directions for two different values.
%   Pred  signed predicate id of a binary closed predicate proved asymmetric.
% The reversed-pair check is owned by pruning/properties/antisymmetric.lp.
antisymmetric_pred(Pred) :- asymmetric_pred(Pred).

% ----- pruning/properties/total_order.lp -----

% DEFINITION, reusable property bridge. antisymmetric_pred(Pred): Pred holds
% in both directions only for equal values.
%   Pred  as above.
% The reversed-pair check is owned by pruning/properties/antisymmetric.lp.
antisymmetric_pred(Pred) :- total_order_pred(Pred).

% ----- pruning/properties/arg_distinct.lp -----

% CONSTRAINT. A plain atom may not write one variable at two argument
% positions that always hold different values. Positive, the atom can never
% be true; negated, it is always true and adds nothing.
%   Section, Slot, Mode  the plain atom, of either polarity.
%   Pred                 its predicate.
%   Arg0, Arg1           two argument positions proved distinct.
%   Var                  the single variable id written at both.
% With arg_distinct_pred(parent,0,1) and arg_distinct_pred(move,0,2):
%   pruned: :- d(V0), not parent(V0,V0).      always true
%   pruned: :- move(V0,V1,V0).                never true
%   kept:   :- parent(V0,V1).
% A positive body self-pair of an irreflexive binary predicate is left to
% pruning/properties/irreflexive.lp.
:- selected(Section, Slot, Mode),
    normal_literal(Section, Slot, Mode, Pred, _),
    arg_distinct_pred(Pred, Arg0, Arg1),
    var_at(Section, Slot, Arg0, Var),
    var_at(Section, Slot, Arg1, Var),
    not arg_distinct_self_pair_owned_by_irreflexive(Slot, Mode, Pred).

% Closed-world argument distinctness property.
%
% Python emits arg_distinct_pred(Pred, Arg0, Arg1) when every true tuple of
% predicate Pred has different values at positions Arg0 and Arg1. Other
% property files may derive arg_distinct_pred/3 when they imply it; for example
% irreflexive.lp derives arg_distinct_pred(Pred, 0, 1) for binary predicates.
% This file rejects generated literals that assign the same variable to those
% positions.

% DEFINITION, local helper. arg_distinct_self_pair_owned_by_irreflexive(Slot,
% Mode, Pred): the literal is a positive body atom of an irreflexive binary
% predicate, whose self-pair irreflexive.lp already rejects.
%   Slot  body slot of the atom.
%   Mode  its mode id.
%   Pred  its predicate, binary and irreflexive.
% Used only, negated, by the constraint below, so that one clause is not
% rejected by two constraints for the same reason.
arg_distinct_self_pair_owned_by_irreflexive(Slot, Mode, Pred) :-
    positive_body_literal(Slot, Mode, Pred, 2),
    irreflexive_pred(Pred).

% CONSTRAINT. The same check inside an aggregate: a condition atom may not
% write one variable at two positions that always differ, since the condition
% would never hold.
%   Slot                  body slot of an aggregate of the single-element
%                         subset.
%   Condition, Pred       a condition occurrence and its predicate.
%   LocalArg0, LocalArg1  two argument positions of Pred proved distinct.
%   Var                   the single variable id written at both.
% With arg_distinct_pred(parent,0,1):
%   pruned: #count{V0 : parent(V0,V0)} = V1
%   kept:   #count{V0 : parent(V0,V1)} = V2
:- selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Pred, _),
    arg_distinct_pred(Pred, LocalArg0, LocalArg1),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg0, Var),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg1, Var).

% ----- pruning/properties/arg_equal.lp -----

% CONSTRAINT. A positive body atom must write the same variable id at two
% argument positions that always hold equal values, when its template lets
% them share a variable. With two ids the atom would force them equal, which
% the enumerator expresses with one id.
%   Slot, Mode  body slot and template of the positive atom.
%   Pred        its predicate.
%   Arg0, Arg1  two argument positions proved equal.
%   Var0, Var1  the two different variable ids found there.
% With arg_equal_pred(same,0,1):
%   pruned: h(V0) :- same(V0,V1).
%   kept:   h(V0) :- same(V0,V0).
%   kept:   h(V0) :- d(V0), d(V1), not same(V0,V1).   negation is not covered
%   kept:   :- same(V0,V1), a(V0).    when same is declared
%           same(var(a,any),var(b,any)): same(V0,V0) would mix two types
:- positive_body_literal(Slot, Mode, Pred, _),
    arg_equal_pred(Pred, Arg0, Arg1),
    not arg_equal_unshareable(Mode, Arg0, Arg1),
    var_at(body, Slot, Arg0, Var0),
    var_at(body, Slot, Arg1, Var1),
    Var0 != Var1.

% Closed-world argument equality property.
%
% Python emits arg_equal_pred(Pred, Arg0, Arg1) when every true tuple of predicate
% Pred has equal values at argument positions Arg0 and Arg1. The enumerator
% chooses identical variable ids at these positions of positive literals, which
% can only be true for equal values. A negated literal with distinct ids is not
% equivalent: not same(X,Y) holds for every X != Y.
%
% One variable id is only possible where the template allows it. Two positions
% with different declared types (legality/typing.lp) or different labels
% (legality/labels.lp) can never share a variable, so there the atom keeps two
% ids and states the equality of their values by itself. Without this
% exception such a predicate could not appear in any clause.

% DEFINITION, local helper. arg_equal_unshareable(Mode, Arg0, Arg1): the two
% equal-valued argument positions of this atom template cannot hold one
% variable.
%   Mode        id of a template whose atom has the arg_equal property.
%   Arg0, Arg1  the two argument positions proved equal.
% Used only, negated, by the first constraint below.
% Case 1: the positions declare different nominal types.
arg_equal_unshareable(Mode, Arg0, Arg1) :-
    mode_atom(Mode, Pred, _),
    arg_equal_pred(Pred, Arg0, Arg1),
    mode_arg_type(Mode, Arg0, Type0),
    mode_arg_type(Mode, Arg1, Type1),
    Type0 != Type1.

% DEFINITION, local helper. Same predicate. Case 2: the positions carry
% different labels, which must name different variables.
arg_equal_unshareable(Mode, Arg0, Arg1) :-
    mode_atom(Mode, Pred, _),
    arg_equal_pred(Pred, Arg0, Arg1),
    mode_arg_label(Mode, Arg0, Label0),
    mode_arg_label(Mode, Arg1, Label1),
    Label0 != Label1.

% CONSTRAINT. The same check inside an aggregate: a condition atom must write
% one variable id at two argument positions that always hold equal values,
% when its template lets them share a variable.
%   Slot                  body slot of an aggregate of the single-element
%                         subset.
%   Condition, Pred       a condition occurrence and its predicate.
%   LocalArg0, LocalArg1  two argument positions of Pred proved equal.
%   Var0, Var1            the two different variable ids found there.
% With arg_equal_pred(same,0,1):
%   pruned: #count{V0,V1 : same(V0,V1)} = V2
%   kept:   #count{V0 : same(V0,V0)} = V1     by this constraint; the policy in
%           pruning/policies/aggregates.lp then rejects the repeated V0
:- selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Pred, _),
    arg_equal_pred(Pred, LocalArg0, LocalArg1),
    not arg_equal_condition_unshareable(Mode, Condition, LocalArg0, LocalArg1),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg0, Var0),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg1, Var1),
    Var0 != Var1.

% DEFINITION, local helper. arg_equal_condition_unshareable(Mode, Condition,
% LocalArg0, LocalArg1): the same obstacle for one condition atom of an
% aggregate template.
%   Mode                  id of an aggregate template of the single-element
%                         subset.
%   Condition             index of a condition whose atom has the property.
%   LocalArg0, LocalArg1  the two argument positions of that atom proved
%                         equal; their types and labels are read at the
%                         flattened positions they map to.
% Used only, negated, by the second constraint below.
% Case 1: different nominal types.
arg_equal_condition_unshareable(Mode, Condition, LocalArg0, LocalArg1) :-
    aggregate_condition_atom(Mode, Condition, Pred, _),
    arg_equal_pred(Pred, LocalArg0, LocalArg1),
    mode_aggregate_condition_arg(Mode, Condition, LocalArg0, Position0),
    mode_aggregate_condition_arg(Mode, Condition, LocalArg1, Position1),
    mode_arg_type(Mode, Position0, Type0),
    mode_arg_type(Mode, Position1, Type1),
    Type0 != Type1.

% DEFINITION, local helper. Same predicate. Case 2: different labels.
arg_equal_condition_unshareable(Mode, Condition, LocalArg0, LocalArg1) :-
    aggregate_condition_atom(Mode, Condition, Pred, _),
    arg_equal_pred(Pred, LocalArg0, LocalArg1),
    mode_aggregate_condition_arg(Mode, Condition, LocalArg0, Position0),
    mode_aggregate_condition_arg(Mode, Condition, LocalArg1, Position1),
    mode_arg_label(Mode, Position0, Label0),
    mode_arg_label(Mode, Position1, Label1),
    Label0 != Label1.

% ----- pruning/properties/cardinality_upper.lp -----

% CONSTRAINT. The body may not require more provably different tuples of a
% predicate than the predicate can have.
%   Pred   the predicate.
%   Upper  its proved maximum number of tuples.
%   Count  its positive body atoms, all pairwise proved distinct.
% With cardinality_upper_pred(root,1):
%   pruned: :- root(V0), root(V1), V0 != V1.    two different roots cannot exist
%   kept:   :- root(V0), root(V1), e(V0,V1).    V0 and V1 may be the same root
:- cardinality_upper_pred(Pred, Upper),
    positive_body_cardinality(Pred, Count),
    Count > Upper,
    not cardinality_upper_not_pairwise_distinct(Pred).

% DEFINITION, local helper. cardinality_upper_not_pairwise_distinct(Pred):
% some two positive atoms of Pred might denote the same tuple.
%   Pred  a predicate with two positive body atoms not proved distinct.
% Used only, negated, by the constraint below.
cardinality_upper_not_pairwise_distinct(Pred) :-
    cardinality_upper_pred(Pred, _),
    positive_body_literal(Slot0, _, Pred, Arity),
    positive_body_literal(Slot1, _, Pred, Arity),
    Slot0 < Slot1,
    not positive_body_tuple_known_distinct(Pred, Slot0, Slot1).

% Exceeding a predicate cardinality cap is impossible only when all selected
% positive tuples are provably pairwise distinct. Different variable names alone
% do not establish distinct ground values.

% DEFINITION, local helper. positive_body_tuple_known_distinct(Pred, Slot0,
% Slot1): two positive atoms of Pred certainly denote different tuples.
%   Pred           the predicate of both atoms, one with a cardinality cap;
%                  nothing is derived for predicates without one.
%   Slot0 < Slot1  their body slots.
% It holds when, at some argument position, the two atoms hold variables the
% clause proves unequal (known_unequal_values: an explicit "!=" or "<").
% Used only, negated, by the next rule.
positive_body_tuple_known_distinct(Pred, Slot0, Slot1) :-
    cardinality_upper_pred(Pred, _),
    positive_body_literal(Slot0, _, Pred, Arity),
    positive_body_literal(Slot1, _, Pred, Arity),
    Slot0 < Slot1,
    Arg = 0..Arity-1,
    var_at(body, Slot0, Arg, Left),
    var_at(body, Slot1, Arg, Right),
    known_unequal_values(Left, Right).

% DEFINITION, local helper. positive_body_cardinality(Pred, Count): how many
% positive body atoms of Pred the clause has.
%   Pred   a predicate with a proved cardinality cap.
%   Count  number of body slots holding a positive atom of Pred.
% Used only by the constraint below.
positive_body_cardinality(Pred, Count) :-
    cardinality_upper_pred(Pred, _),
    Count = #count{Slot : positive_body_literal(Slot, _, Pred, _)}.

% ----- pruning/properties/complement.lp -----

% CONSTRAINT. Both members of a complement pair may not be denied for the
% same tuple when that tuple certainly lies in their shared domain: one of
% the two holds there, so the body could never be satisfied.
%   Slot0 < Slot1  body slots of the two negated atoms, with identical
%                  arguments.
%   Pred0, Pred1   a complement pair.
%   Domain         their shared domain; every argument of the atom at Slot0
%                  must be a variable bound inside it by a positive atom.
%   pruned and kept: see the example in the file header.
:- negative_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 < Slot1,
    complement_domain(Pred0, Pred1, Domain),
    same_term_bindings(body, Slot0, body, Slot1),
    not domain_literal_uncovered(Domain, Slot0).

% DEFINITION, local helper. complement_domain(Pred0, Pred1, Domain): the
% domain over which two predicates are complementary, available for either
% order of the pair.
%   Pred0, Pred1  the two predicates, in the order the constraint meets them.
%   Domain        the term complement(A, B), with A and B in the order Python
%                 emitted; domain_cover/4 facts refer to that exact term.
% Used only by the constraint below.
% Case 1: the pair in the emitted order.
complement_domain(Pred0, Pred1, complement(Pred0, Pred1)) :-
    complement_pred(Pred0, Pred1).

% DEFINITION, local helper. Same predicate. Case 2: the pair reversed; the
% Domain term keeps the emitted order.
complement_domain(Pred1, Pred0, complement(Pred0, Pred1)) :-
    complement_pred(Pred0, Pred1).

% ----- pruning/properties/disjoint.lp -----

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

% ----- pruning/properties/empty.lp -----

% Closed-world empty predicate property.
%
% Python emits empty_pred(Pred) when predicate Pred has no true ground facts in
% the closed-world evidence. Positive uses are impossible; negative uses are
% redundant because not Pred(...) is always true.

% CONSTRAINT. A positive body atom of an empty predicate makes the body
% unsatisfiable.
%   Slot  body slot of the positive atom.
%   Pred  its predicate, proved empty.
% With empty_pred(broken):
%   pruned: h(V0) :- d(V0), broken(V0).
%   kept:   h(V0) :- d(V0).
:- positive_body_literal(Slot, _, Pred, _),
    empty_pred(Pred).

% CONSTRAINT. A negated body atom of an empty predicate is always true and
% adds nothing.
%   Slot  body slot of the negated atom.
%   Pred  its predicate, proved empty.
% With empty_pred(broken):
%   pruned: h(V0) :- d(V0), not broken(V0).
%   kept:   h(V0) :- d(V0).
% Together the two constraints leave no body atom of an empty predicate.
:- negative_body_literal(Slot, _, Pred, _),
    empty_pred(Pred).

% ----- pruning/properties/equivalent.lp -----

% CONSTRAINT. Two equivalent predicates may not both be negated on the same
% arguments: the second negation repeats the first.
%   Slot0 < Slot1  body slots of the two negated atoms, with identical
%                  arguments.
%   Pred0, Pred1   an equivalent pair.
% With equivalent_pred(adult,grown):
%   pruned: h(V0) :- d(V0), not adult(V0), not grown(V0).
%   kept:   h(V0) :- d(V0), not adult(V0).
:- negative_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 < Slot1,
    equivalent_pair(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).

% Closed-world equivalent predicate property.
%
% Python emits equivalent_pred(Pred0, Pred1) when two predicates with same arity
% have identical truth values for same argument tuple. Equivalence is
% implication in both directions, so this file exports implies_pred/2. It keeps
% only equivalent-specific duplicate pruning that implication cannot express:
% duplicate negated body literals. Head predicates are learned, so no property
% fact ever names them.

% DEFINITION, local helper. equivalent_pair(Pred0, Pred1): the two predicates
% are equivalent, available in both orders.
%   Pred0, Pred1  signed predicate ids of an equivalent pair.
% Python emits each pair once; the constraint below must match whichever
% predicate sits in the earlier slot. Used only by that constraint.
% Case 1: the emitted order.
equivalent_pair(Pred0, Pred1) :- equivalent_pred(Pred0, Pred1).

% DEFINITION, local helper. Same predicate. Case 2: the reversed order.
equivalent_pair(Pred1, Pred0) :- equivalent_pred(Pred0, Pred1).

% ----- pruning/properties/functional.lp -----

% Closed-world single-input functional dependency property.
%
% Python emits functional_pred(Pred, Input, Output) when predicate Pred maps each
% value at argument Input to only one value at argument Output. Positive pairs
% with distinct output ids are excluded by the variable-identification policy:
% the dependency equates their values, not their syntactic ids. Negative-pair
% pruning instead requires a proof that the output values differ.

% CONSTRAINT. Two positive atoms of a functional predicate that share the
% input variable must share the output variable. With two output ids the
% dependency would force them equal, which the enumerator expresses with one.
%   Slot0 < Slot1  body slots of the two positive atoms.
%   Pred           the predicate.
%   Input, Output  argument positions: Input determines Output.
%   Same           the variable id both atoms hold at Input.
%   Out0, Out1     the two different variable ids they hold at Output.
% With functional_pred(mother,0,1) (each child has one mother):
%   pruned: h(V0) :- mother(V0,V1), mother(V0,V2), r(V1,V2).
%   kept:   h(V0) :- mother(V0,V1), r(V1,V1).       the same meaning
%   kept:   h(V0) :- mother(V0,V1), mother(V2,V1).  the inputs differ
:- positive_body_literal(Slot0, _, Pred, _),
    positive_body_literal(Slot1, _, Pred, _),
    Slot0 < Slot1,
    functional_pred(Pred, Input, Output),
    var_at(body, Slot0, Input, Same),
    var_at(body, Slot1, Input, Same),
    var_at(body, Slot0, Output, Out0),
    arg(body, Slot1, Output),
    not var_at(body, Slot1, Output, Out0).

% A negative tuple with a provably different output is already implied by the positive tuple.

% CONSTRAINT. After a positive atom of a functional predicate, negating the
% same input with a provably different output is always true and adds
% nothing.
%   PosSlot, NegSlot  body slots of the positive and the negated atom.
%   Input, Output     argument positions: Input determines Output.
%   Same              the variable id both atoms hold at Input.
%   Out0, Out1        their output variable ids, proved unequal in value by
%                     an explicit "!=" or "<" (known_unequal_values).
% With functional_pred(mother,0,1):
%   pruned: :- mother(V0,V1), w(V2), V1 != V2, not mother(V0,V2).
%   kept:   :- mother(V0,V1), w(V2), not mother(V0,V2).   V2 may equal V1
:- positive_body_literal(PosSlot, _, Pred, _),
    negative_body_literal(NegSlot, _, Pred, _),
    functional_pred(Pred, Input, Output),
    var_at(body, PosSlot, Input, Same),
    var_at(body, NegSlot, Input, Same),
    var_at(body, PosSlot, Output, Out0),
    var_at(body, NegSlot, Output, Out1),
    known_unequal_values(Out0, Out1).

% ----- pruning/properties/functional_set.lp -----

% CONSTRAINT. Two positive atoms of a predicate that share every determining
% variable must share the determined variable. With two output ids the
% dependency would force them equal, which the enumerator expresses with one.
%   Slot0 < Slot1  body slots of the two positive atoms.
%   Pred           the predicate.
%   Fd             a dependency of Pred whose inputs are all shared.
%   Output         the argument position it determines.
%   Out0, Out1     the two different variable ids found there.
% With arguments 0 and 1 of grade(Student,Course,Mark) determining argument 2:
%   pruned: :- grade(V0,V1,V2), grade(V0,V1,V3), r(V2,V3).
%   kept:   :- grade(V0,V1,V2), grade(V0,V3,V4).    the course differs
:- positive_body_literal(Slot0, _, Pred, _),
    positive_body_literal(Slot1, _, Pred, _),
    Slot0 < Slot1,
    functional_set_pred(Pred, Fd, Output),
    not fd_inputs_differ(Slot0, Slot1, Fd),
    var_at(body, Slot0, Output, Out0),
    arg(body, Slot1, Output),
    not var_at(body, Slot1, Output, Out0).

% A negative tuple with a provably different output is already implied by the positive tuple.

% CONSTRAINT. After a positive atom, negating the same determining arguments
% with a provably different determined value is always true and adds nothing.
%   PosSlot, NegSlot  body slots of the positive and the negated atom.
%   Fd, Output        a dependency of Pred whose inputs are all shared, and
%                     the position it determines.
%   Out0, Out1        the output variable ids, proved unequal in value by an
%                     explicit "!=" or "<" (known_unequal_values).
% With the same dependency of grade/3:
%   pruned: :- grade(V0,V1,V2), m(V3), V2 != V3, not grade(V0,V1,V3).
%   kept:   :- grade(V0,V1,V2), m(V3), not grade(V0,V1,V3).   V3 may equal V2
:- positive_body_literal(PosSlot, _, Pred, _),
    negative_body_literal(NegSlot, _, Pred, _),
    functional_set_pred(Pred, Fd, Output),
    not fd_inputs_differ(PosSlot, NegSlot, Fd),
    var_at(body, PosSlot, Output, Out0),
    var_at(body, NegSlot, Output, Out1),
    known_unequal_values(Out0, Out1).

% ----- representation/operators.lp -----

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

% ----- pruning/properties/functional_set.lp -----

% Closed-world composite functional dependency property.
%
% Python emits functional_set_pred(Pred, Fd, Output) and functional_set_arg(Fd, Input)
% when a set of input arguments functionally determines one output argument.
% Positive pairs with the same determinant bindings and different output ids
% are excluded by the variable-identification policy, not because different ids
% prove different values. Negative-pair pruning requires known unequal values.

% DEFINITION, local helper. fd_inputs_differ(Slot0, Slot1, Fd): two body
% literals do not share all determining arguments of a dependency.
%   Slot0, Slot1  two body slots.
%   Fd            id of a dependency: an integer emitted by Python, or
%                 key(Key) derived by pruning/properties/key.lp.
% It holds when some input position of Fd carries different variable ids in
% the two literals. It is derived only for the pairs the constraints below
% inspect: a positive atom at Slot0 and a plain atom of either polarity at
% Slot1, both of a predicate that has the dependency. Used only, negated, by
% those constraints.
fd_inputs_differ(Slot0, Slot1, Fd) :-
    positive_body_literal(Slot0, _, Pred, _),
    normal_literal(body, Slot1, _, Pred, _),
    functional_set_pred(Pred, Fd, _),
    functional_set_arg(Fd, Input),
    var_at(body, Slot0, Input, Var),
    arg(body, Slot1, Input),
    not var_at(body, Slot1, Input, Var).

% ----- pruning/properties/key.lp -----

% Closed-world key property.
%
% Python emits key_pred(Pred, Key) plus key_arg(Key, Arg) when the listed argument
% positions form a key for predicate Pred. Two true Pred tuples cannot share all
% key arguments while differing elsewhere. A key is a functional dependency from
% key arguments to every non-key argument, so this file exports
% functional_set_pred/3 and functional_set_arg/2 instead of duplicating
% functional dependency pruning here.
%
% This file has no constraint of its own.

% The symbolic id key(Key) cannot collide with Python's integer dependency ids.

% DEFINITION, reusable property bridge. functional_set_arg(key(Key), Arg): a
% determining position of the dependency that a key induces.
%   key(Key)  dependency id built from the key id.
%   Arg       an argument position that belongs to the key.
% Consumed by pruning/properties/functional_set.lp.
functional_set_arg(key(Key), Arg) :- key_arg(Key, Arg).

% DEFINITION, reusable property bridge. functional_set_pred(Pred, key(Key),
% Output): the key of Pred determines its argument Output.
%   Pred      signed predicate id with key Key.
%   key(Key)  the dependency id.
%   Output    each argument position of Pred outside the key.
% The arity comes from a selected positive body atom of Pred, so the facts
% exist only in models that use Pred. With key {0} of person(Id,Name,Age),
% positions 1 and 2 are determined, and functional_set.lp then prunes
% "person(V0,V1,V2), person(V0,V3,V4)".
functional_set_pred(Pred, key(Key), Output) :-
    positive_body_literal(_, _, Pred, Arity),
    key_pred(Pred, Key),
    Output = 0..Arity-1,
    not key_arg(Key, Output).

% ----- pruning/properties/implies.lp -----

% Closed-world implication property.
%
% Python emits implies_pred(Pred0, Pred1) when Pred0(X...) implies Pred1(X...)
% for same-arity predicates. Other property files may derive implies_pred/2
% when they imply it. Target may be a learned predicate whose background lower
% bound already contains Source: learned clauses only add to it. This file prunes
% body literals made redundant or impossible by a positive body literal, and a
% plain head that the body already guarantees. A choice or aggregate head is not
% redundant that way: 0{q(X);s(X)}1 :- p(X) still forbids s(X) when p implies q.
%
% The examples assume implies_pred(parent,ancestor): every parent tuple is an
% ancestor tuple.

% CONSTRAINT. A positive body atom already implied by another positive body
% atom on the same arguments is redundant.
%   Slot0         body slot of the implying atom, of Pred0.
%   Slot1         a different body slot, of the implied atom of Pred1.
%   Pred0, Pred1  predicates with Pred0 implying Pred1.
%   pruned: h(V0) :- parent(V0,V1), ancestor(V0,V1).
%   kept:   h(V0) :- parent(V0,V1).                     the same meaning
%   kept:   h(V0) :- parent(V0,V1), ancestor(V1,V0).    different arguments
% The rejected atom must not be needed by directed flow (legality/flow/
% removal.lp): otherwise the shorter clause is not in the language and this
% one has to stay.
%   kept:   h(V0) :- node(V0), red(V0).    with node(output), red(input) and
%           red implying node: node(V0) is what binds the input of red
:- positive_body_literal(Slot0, _, Pred0, Arity),
    positive_body_literal(Slot1, _, Pred1, Arity),
    Slot0 != Slot1,
    implies_pred(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1),
    not flow_needed(Slot1).

% CONSTRAINT. A plain or disjunctive head atom that a positive body atom
% already implies on the same arguments makes the clause derive nothing new.
%   Slot0        body slot of the implying atom, of Pred0.
%   Slot1, Mode  head slot and mode of the implied atom of Pred1; an
%                unconditional atom of a normal or disjunctive head.
% Here ancestor is learnable and the background already derives it from
% parent, which is why the implication is proved:
%   pruned: ancestor(V0,V1) :- parent(V0,V1).       already in the background
%   kept:   ancestor(V0,V2) :- parent(V0,V1), ancestor(V1,V2).
%   kept:   {ancestor(V0,V1)} :- parent(V0,V1).     choice heads are not pruned
:- positive_body_literal(Slot0, _, Pred0, Arity),
    head_literal(Slot1, Mode, Pred1, Arity),
    plain_disjunctive_head_mode(Mode),
    implies_pred(Pred0, Pred1),
    same_term_bindings(body, Slot0, head, Slot1).

% CONSTRAINT. A positive body atom together with the negation of what it
% implies, on the same arguments, makes the body unsatisfiable.
%   Slot0  body slot of the positive atom, of Pred0.
%   Slot1  a different body slot, of the negated atom of Pred1.
%   pruned: h(V0) :- parent(V0,V1), not ancestor(V0,V1).
%   kept:   h(V0) :- ancestor(V0,V1), not parent(V0,V1).   the converse is fine
:- positive_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 != Slot1,
    implies_pred(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).

% ----- pruning/properties/equivalent.lp -----

% DEFINITION, reusable property bridge. implies_pred(Pred0, Pred1): every
% tuple of Pred0 is a tuple of Pred1.
%   Pred0, Pred1  signed predicate ids of an equivalent pair.
% Equivalence is implication both ways. The positive-literal checks are owned
% by pruning/properties/implies.lp.
% Case 1: left implies right.
implies_pred(Pred0, Pred1) :- equivalent_pred(Pred0, Pred1).

% DEFINITION, reusable property bridge. Same predicate. Case 2: right implies
% left.
implies_pred(Pred1, Pred0) :- equivalent_pred(Pred0, Pred1).

% ----- pruning/properties/inverse.lp -----

% CONSTRAINT. A positive atom and the positive atom of its inverse over the
% swapped variables say the same thing; one of them is redundant. Here the
% later atom is the one that directed flow does not need.
%   Slot0, Slot1  the duplicated pair.
%   pruned: h(V0) :- parent(V0,V1), child(V1,V0).
%   kept:   h(V0) :- parent(V0,V1).                  the same meaning
%   kept:   h(V0) :- parent(V0,V1), child(V0,V1).    not swapped
:- inverse_duplicate(Slot0, Slot1), not flow_needed(Slot1).

% CONSTRAINT. The same pair when the earlier atom is the one that directed
% flow does not need. The clause stays only if both atoms are needed.
%   Slot0, Slot1  the duplicated pair.
:- inverse_duplicate(Slot0, Slot1), not flow_needed(Slot0).

% DEFINITION, local helper. inverse_duplicate(Slot0, Slot1): two positive
% body atoms of an inverse pair say the same thing.
%   Slot0 < Slot1  body slots of the two positive binary atoms, over swapped
%                  variables.
% Used only by the two constraints below, which differ in which of the two
% atoms the shorter clause would lose.
inverse_duplicate(Slot0, Slot1) :-
    positive_body_literal(Slot0, _, _, 2),
    positive_body_literal(Slot1, _, _, 2),
    Slot0 < Slot1,
    inverse_swapped(Slot0, Slot1).

% CONSTRAINT. A positive atom together with the negation of its inverse over
% the swapped variables makes the body unsatisfiable.
%   Slot0  body slot of the positive atom, of Pred0.
%   Slot1  body slot of the negated atom, of Pred1.
%   pruned: h(V0) :- parent(V0,V1), not child(V1,V0).
%   kept:   h(V0) :- parent(V0,V1), not child(V0,V1).
:- positive_body_literal(Slot0, _, Pred0, 2),
    negative_body_literal(Slot1, _, Pred1, 2),
    inverse_swapped(Slot0, Slot1).

% DEFINITION, local helper. inverse_swapped(Slot0, Slot1): two body atoms of
% an inverse pair hold the same two variables, swapped.
%   Slot0  body slot of a plain atom Pred0(Left, Right), of either polarity.
%   Slot1  a different body slot, of a plain atom Pred1(Right, Left) whose
%          predicate is the inverse of Pred0.
% Example: parent(V0,V1) and child(V1,V0). It is derived only for inverse
% pairs, so tasks without them ground nothing. Used only by the two
% constraints below.
inverse_swapped(Slot0, Slot1) :-
    normal_literal(body, Slot0, _, Pred0, 2),
    normal_literal(body, Slot1, _, Pred1, 2),
    inverse_pair(Pred0, Pred1),
    Slot0 != Slot1,
    var_at(body, Slot0, 0, Left),
    var_at(body, Slot0, 1, Right),
    var_at(body, Slot1, 0, Right),
    var_at(body, Slot1, 1, Left).

% Closed-world inverse predicate property.
%
% Python emits inverse_pred(Pred0, Pred1) when two binary predicates are inverses:
% Pred0(X, Y) has same truth value as Pred1(Y, X). This file removes redundant
% positive inverse pairs and contradictory positive/negative inverse pairs.
%
% The examples assume inverse_pred(parent,child).

% DEFINITION, local helper. inverse_pair(Pred0, Pred1): the two predicates are
% inverses, available in both orders.
%   Pred0, Pred1  signed predicate ids of an inverse pair.
% Python emits each pair once; the constraints below must match whichever
% predicate they meet first. Used only by those constraints.
% Case 1: the emitted order.
inverse_pair(Pred0, Pred1) :- inverse_pred(Pred0, Pred1).

% DEFINITION, local helper. Same predicate. Case 2: the reversed order.
inverse_pair(Pred1, Pred0) :- inverse_pred(Pred0, Pred1).

% ----- pruning/properties/irreflexive.lp -----

% CONSTRAINT. A positive body atom of an irreflexive predicate may not relate
% a variable to itself: it could never be true.
%   Slot  body slot of the positive binary atom.
%   Pred  its predicate, irreflexive.
%   Var   the single variable id written at both arguments.
% With before/2 irreflexive:
%   pruned: h(V0) :- before(V0,V0).
%   kept:   h(V0) :- before(V0,V1).
:- positive_body_literal(Slot, _, Pred, 2),
    irreflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var).

% ----- pruning/properties/mutex.lp -----

% CONSTRAINT. Two mutex predicates may not both be required on the same
% arguments: the body could never hold.
%   Slot0 < Slot1  body slots of the two positive atoms, with identical
%                  arguments.
%   Pred0, Pred1   a mutex pair.
% With mutex_pred(red,green):
%   pruned: h(V0) :- red(V0), green(V0).
%   kept:   h(V0) :- red(V0), green(V1), e(V0,V1).   different arguments
:- positive_body_literal(Slot0, _, Pred0, Arity),
    positive_body_literal(Slot1, _, Pred1, Arity),
    Slot0 < Slot1,
    mutex_pair(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).

% CONSTRAINT. After a positive atom, negating its mutex partner on the same
% arguments is always true and adds nothing.
%   Slot0  body slot of the positive atom, of Pred0.
%   Slot1  a different body slot, of the negated atom of Pred1.
% With mutex_pred(red,green):
%   pruned: h(V0) :- red(V0), not green(V0).
%   kept:   h(V0) :- red(V0).                       the same meaning
%   kept:   h(V0) :- d(V0), not red(V0), not green(V0).   two negations stay
:- positive_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 != Slot1,
    mutex_pair(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).

% DEFINITION, local helper. mutex_pair(Pred0, Pred1): the two predicates are
% mutex, available in both orders.
%   Pred0, Pred1  signed predicate ids of a mutex pair.
% Each pair is stated once; the constraints below must match whichever
% predicate they meet first. Used only by those constraints.
% Case 1: the stated order.
mutex_pair(Pred0, Pred1) :- mutex_pred(Pred0, Pred1).

% DEFINITION, local helper. Same predicate. Case 2: the reversed order.
mutex_pair(Pred1, Pred0) :- mutex_pred(Pred0, Pred1).

% ----- pruning/properties/complement.lp -----

% Closed-world complement predicate property.
%
% Python emits complement_pred(Pred0, Pred1) when same-arity predicates are
% disjoint and their union is the product of its argument values. Complements
% are also mutex, so this file exports mutex_pred/2. Denying both is impossible
% only for a tuple inside that product (see domains.lp):
%   a(1). b(2). c(1). c(2). e(5,5).
%   h(X) :- c(X), not a(X), not b(X).       pruned: c only reaches 1 and 2
%   h(X) :- e(X,X), not a(X), not b(X).     kept: X = 5 is neither a nor b

% DEFINITION, reusable property bridge. mutex_pred(Pred0, Pred1): the two
% predicates never hold for the same tuple.
%   Pred0, Pred1  signed predicate ids of a complement pair.
% Complements are disjoint by definition. The shared checks (both positive,
% or one positive and the other negated) are owned by
% pruning/properties/mutex.lp.
mutex_pred(Pred0, Pred1) :- complement_pred(Pred0, Pred1).

% ----- pruning/properties/mutex.lp -----

% Mutex predicates cannot both hold on the same terms. A positive member also
% makes negation of its partner redundant. Strong complements p/n and -p/n use
% this same rule; two default-negated members remain available.

% DEFINITION, reusable property bridge. mutex_pred(Pred0, Pred1): the two
% predicates never hold for the same tuple.
%   Pred0  signed predicate id of p/n.
%   Pred1  signed predicate id of its strong negation -p/n.
% ASP coherence forbids p(t) together with -p(t), so the pair is mutex in
% every task. mutex_pred/2 is also emitted by Python and derived by
% complement.lp and partition.lp.
mutex_pred(Pred0, Pred1) :- strong_complement_pred(Pred0, Pred1).

% ----- pruning/properties/partition.lp -----

% Closed-world partition property.
%
% Python emits partition_pred(Part, Pred) for each predicate Pred in a partition
% Part where exactly one member predicate is true for each tuple of the product
% of the members' argument values. This file prunes sets of negated partition
% members that deny the whole partition for a tuple inside that product (see
% domains.lp); outside it every member can be false. Different
% members of one partition are mutex, so this file exports mutex_pred/2 instead
% of duplicating mutex pruning here.
%
% The examples assume the partition {red, green, blue}.

% DEFINITION, reusable property bridge. mutex_pred(Pred0, Pred1): two
% different members of one partition never hold for the same tuple.
%   Pred0, Pred1  signed predicate ids of two members of partition Part;
%                 "Pred0 < Pred1" states each pair once.
% The shared checks are owned by pruning/properties/mutex.lp.
mutex_pred(Pred0, Pred1) :-
    partition_pred(Part, Pred0),
    partition_pred(Part, Pred1),
    Pred0 < Pred1.

% CONSTRAINT. The body may not deny every member of a partition for a tuple
% that certainly lies in the partition's domain: exactly one member holds
% there, so the body could never be satisfied.
%   Anchor      body slot of a negated member atom.
%   AnchorPred  its predicate.
%   Part        the partition, all of whose members are negated on the
%               anchor's arguments; every argument of the anchor must be a
%               variable bound inside the domain by a positive atom.
% With node(V0) binding V0 inside the partition's domain:
%   pruned: :- node(V0), not red(V0), not green(V0), not blue(V0).
%   kept:   :- node(V0), not red(V0), not green(V0).      blue remains possible
%   kept:   :- w(V0), not red(V0), not green(V0), not blue(V0).
%           when w can reach values outside the domain
:- negative_body_literal(Anchor, _, AnchorPred, _),
    partition_pred(Part, AnchorPred),
    not partition_neg_missing(Part, Anchor),
    not domain_literal_uncovered(partition(Part), Anchor).

% DEFINITION, local helper. partition_neg_missing(Part, Anchor): some member
% of the partition is not negated on the anchor's arguments.
%   Part, Anchor  as above.
% Used only, negated, by the constraint below.
partition_neg_missing(Part, Anchor) :-
    negative_body_literal(Anchor, _, AnchorPred, _),
    partition_pred(Part, AnchorPred),
    partition_pred(Part, Pred),
    not partition_neg_has(Part, Anchor, Pred).

% DEFINITION, local helper. partition_neg_has(Part, Anchor, Pred): the body
% negates member Pred on the arguments of the negated atom at Anchor.
%   Part    id of a partition.
%   Anchor  body slot of a negated atom of some member of Part; its arguments
%           are the tuple being examined.
%   Pred    a member of Part negated on exactly those arguments.
% Used only, negated, by partition_neg_missing below.
% Case 1: the anchor atom itself.
partition_neg_has(Part, Anchor, AnchorPred) :-
    negative_body_literal(Anchor, _, AnchorPred, _),
    partition_pred(Part, AnchorPred).

% DEFINITION, local helper. Same predicate. Case 2: another negated atom of a
% member of Part with the same arguments as the anchor.
%   Slot  (body variable) body slot of that other negated atom.
partition_neg_has(Part, Anchor, Pred) :-
    negative_body_literal(Anchor, _, AnchorPred, Arity),
    negative_body_literal(Slot, _, Pred, Arity),
    partition_pred(Part, AnchorPred),
    partition_pred(Part, Pred),
    same_term_bindings(body, Anchor, body, Slot).

% ----- pruning/properties/project_implies.lp -----

% CONSTRAINT. A positive body atom that is the projection of another positive
% body atom is redundant.
%   Slot0         body slot of the source atom, of Pred0.
%   Slot1         a different body slot, of the target atom of Pred1.
%   Projection    the projection from Pred0 to Pred1 that aligns them.
%   pruned: h(V0) :- edge(V0,V1), node(V0).
%   kept:   h(V0) :- edge(V0,V1).               the same meaning
%   kept:   h(V0) :- edge(V0,V1), node(V1).     node(V1) is not implied
% The rejected atom must not be needed by directed flow (legality/flow/
% removal.lp): otherwise the shorter clause is not in the language and this
% one has to stay.
:- positive_body_literal(Slot0, _, Pred0, _),
    positive_body_literal(Slot1, _, Pred1, _),
    Slot0 != Slot1,
    project_implies_pred(Pred0, Pred1, Projection),
    project_vars_match(body, Slot0, body, Slot1, Projection),
    not flow_needed(Slot1).

% CONSTRAINT. A positive body atom together with the negation of its
% projection makes the body unsatisfiable.
%   Slot0  body slot of the positive source atom.
%   Slot1  a different body slot, of the negated target atom.
%   pruned: h(V0) :- edge(V0,V1), not node(V0).
%   kept:   h(V0) :- edge(V0,V1), not node(V1).
:- positive_body_literal(Slot0, _, Pred0, _),
    negative_body_literal(Slot1, _, Pred1, _),
    Slot0 != Slot1,
    project_implies_pred(Pred0, Pred1, Projection),
    project_vars_match(body, Slot0, body, Slot1, Projection).

% CONSTRAINT. A plain or disjunctive head atom that is the projection of a
% positive body atom makes the clause derive nothing new.
%   Slot0        body slot of the positive source atom.
%   Slot1, Mode  head slot and mode of the target atom; an unconditional atom
%                of a normal or disjunctive head.
% Here node is learnable and the background already derives node(X) from
% edge(X,Y), which is why the projection is proved:
%   pruned: node(V0) :- edge(V0,V1).            already in the background
%   kept:   node(V1) :- edge(V0,V1).
%   kept:   {node(V0)} :- edge(V0,V1).          choice heads are not pruned
:- positive_body_literal(Slot0, _, Pred0, _),
    head_literal(Slot1, Mode, Pred1, _),
    plain_disjunctive_head_mode(Mode),
    project_implies_pred(Pred0, Pred1, Projection),
    project_vars_match(body, Slot0, head, Slot1, Projection).

% DEFINITION, local helper. project_vars_match(Section0, Slot0, Section1,
% Slot1, Projection): the target literal is exactly the projection of the
% source literal.
%   Section0, Slot0  a plain atom of the source predicate.
%   Section1, Slot1  a plain atom of the target predicate.
%   Projection       a projection from the first predicate to the second
%                    under which every paired position holds the same
%                    variable id.
% Example: edge(V0,V1) and node(V0) match; edge(V0,V1) and node(V1) do not.
% Used only by the three constraints below.
project_vars_match(Section0, Slot0, Section1, Slot1, Projection) :-
    normal_literal(Section0, Slot0, _, Pred0, _),
    normal_literal(Section1, Slot1, _, Pred1, _),
    project_implies_pred(Pred0, Pred1, Projection),
    not project_vars_differ(Section0, Slot0, Section1, Slot1, Projection).

% Closed-world projected implication property.
%
% Python emits project_implies_pred(Pred0, Pred1, Projection) plus project_arg
% facts when Pred0 implies Pred1 after mapping source arguments to target
% arguments. Example: edge(X, Y) may imply node(X) via projection target arg 0
% from source arg 0. Target may be a learned predicate whose background lower
% bound contains the projection; only a plain head is redundant that way.
%
% The examples assume edge(X,Y) implies node(X): project_implies_pred(edge,
% node,p) with project_arg(p,0,0).

% DEFINITION, local helper. project_vars_differ(Section0, Slot0, Section1,
% Slot1, Projection): two literals are not aligned the way a projection
% requires.
%   Section0, Slot0  the literal playing the source.
%   Section1, Slot1  the literal playing the target.
%   Projection       id of a projection. Each project_arg(Projection,
%                    TargetArg, SourceArg) pairs argument SourceArg of the
%                    source with argument TargetArg of the target.
% It holds when some paired positions carry different variable ids. It is
% derived only for the pairs the next rule inspects: two plain atoms whose
% predicates the projection relates. Used only, negated, by that rule.
project_vars_differ(Section0, Slot0, Section1, Slot1, Projection) :-
    normal_literal(Section0, Slot0, _, Pred0, _),
    normal_literal(Section1, Slot1, _, Pred1, _),
    project_implies_pred(Pred0, Pred1, Projection),
    project_arg(Projection, TargetArg, SourceArg),
    var_at(Section0, Slot0, SourceArg, Var),
    arg(Section1, Slot1, TargetArg),
    not var_at(Section1, Slot1, TargetArg, Var).

% ----- pruning/properties/reflexive.lp -----

% Reflexivity holds on the field Python checked (see domains.lp).
% A positive self-pair is redundant when another positive literal binds its
% variable inside that field. A negative self-pair is then impossible.
%   le reflexive on {1,2}:  h(X) :- le(X,Y), le(X,X).   pruned (redundant)
%                           h(X) :- n(X), not le(X,X).  kept when n reaches 3

% CONSTRAINT. A positive self-pair of a reflexive predicate is redundant when
% a different positive body atom already binds its variable inside the field.
%   Slot   body slot of the positive atom Pred(Var,Var).
%   Pred   a reflexive binary predicate.
%   Var    the single variable id written at both arguments.
%   Cover  body slot of another positive atom that binds Var inside
%          field(Pred); it must differ from Slot, since the self-pair cannot
%          justify its own removal.
% The rejected atom must not be needed by directed flow (legality/flow/
% removal.lp): otherwise the shorter clause is not in the language and this
% one has to stay.
% With le/2 reflexive on its field:
%   pruned: h(V0) :- le(V0,V1), le(V0,V0).      V0 is in the field through le(V0,V1)
%   kept:   h(V0) :- le(V0,V0).                 the self-pair is what binds V0
%   kept:   h(V0) :- n(V0), le(V0,V0).          when n can reach values outside
%                                               the field, the atom filters them
:- positive_body_literal(Slot, _, Pred, 2),
    reflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var),
    covered_var(field(Pred), 0, Var, Cover),
    Cover != Slot,
    not flow_needed(Slot).

% CONSTRAINT. A negated self-pair of a reflexive predicate is impossible when
% a positive body atom binds its variable inside the field.
%   Slot  body slot of the negated atom "not Pred(Var,Var)".
%   Pred  a reflexive binary predicate.
%   Var   the single variable id, bound inside field(Pred).
% With le/2 reflexive on its field:
%   pruned: h(V0) :- le(V0,V1), not le(V0,V0).
%   kept:   h(V0) :- n(V0), not le(V0,V0).      when n can reach values outside
%                                               the field
:- negative_body_literal(Slot, _, Pred, 2),
    reflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var),
    covered_var(field(Pred), 0, Var).

% ----- pruning/properties/total_order.lp -----

% Closed-world total order predicate property.
%
% Python emits total_order_pred(Pred) when binary predicate Pred behaves like a
% total order over its field (see domains.lp). A total order is reflexive,
% antisymmetric, and transitive; this file exports those base-property atoms and
% keeps only the totality-specific pruning, which needs both variables inside
% the field: not le(X,Y), not le(Y,X) is satisfiable for values outside it.

% DEFINITION, reusable property bridge. reflexive_pred(Pred): Pred(X,X) holds
% for every X of its field.
%   Pred  signed predicate id of a binary closed predicate proved a total
%         order.
% The self-pair checks are owned by pruning/properties/reflexive.lp.
reflexive_pred(Pred) :- total_order_pred(Pred).

% ----- pruning/properties/subsumption.lp -----

% CONSTRAINT. A positive body atom is rejected as redundant when another
% positive atom of the same predicate is stricter than it.
%   GeneralSlot   body slot of the rejected atom.
%   SpecificSlot  body slot of the stricter atom: it adds some equality, the
%                 general atom has no equality of its own that the specific
%                 one lacks, and every variable of the general atom that is
%                 used elsewhere sits at the same placeholder of the specific
%                 atom.
%   pruned and kept: see the examples in the file header.
% The rejected atom must not be needed by directed flow (legality/flow/
% removal.lp): otherwise the shorter clause is not in the language and this
% one has to stay.
:- subsumption_pair(GeneralSlot, SpecificSlot),
    specific_adds_equality(GeneralSlot, SpecificSlot),
    not general_has_extra_equality(GeneralSlot, SpecificSlot),
    not general_var_unsupported(GeneralSlot, SpecificSlot),
    not flow_needed(GeneralSlot).

% DEFINITION, local helper. specific_adds_equality(GeneralSlot, SpecificSlot):
% the specific atom repeats a variable where the general atom has two.
%   GeneralSlot, SpecificSlot  a subsumption pair.
% It holds when, for some pair of placeholder positions, the specific atom
% holds one variable id at both and the general atom holds two different ids,
% as p(V0,V0) against p(V0,V1). Used only by the constraint below.
specific_adds_equality(GeneralSlot, SpecificSlot) :-
    subsumption_pair(GeneralSlot, SpecificSlot),
    var_at(body, SpecificSlot, Arg0, SpecificVar),
    var_at(body, SpecificSlot, Arg1, SpecificVar),
    Arg0 < Arg1,
    var_at(body, GeneralSlot, Arg0, GeneralVar),
    not var_at(body, GeneralSlot, Arg1, GeneralVar).

% DEFINITION, local helper. general_has_extra_equality(GeneralSlot,
% SpecificSlot): the reverse situation; the general atom repeats a variable
% where the specific atom has two.
%   GeneralSlot, SpecificSlot  a subsumption pair.
% No substitution can then map the general atom onto the specific one: one
% variable would need two images, as p(V0,V0,V1) against p(V0,V1,V1). Used
% only, negated, by the constraint below.
general_has_extra_equality(GeneralSlot, SpecificSlot) :-
    subsumption_pair(GeneralSlot, SpecificSlot),
    var_at(body, GeneralSlot, Arg0, GeneralVar),
    var_at(body, GeneralSlot, Arg1, GeneralVar),
    Arg0 < Arg1,
    var_at(body, SpecificSlot, Arg0, SpecificVar),
    not var_at(body, SpecificSlot, Arg1, SpecificVar).

% Keep every variable needed outside the general literal; otherwise a join is lost.

% DEFINITION, local helper. general_var_unsupported(GeneralSlot,
% SpecificSlot): mapping the general atom onto the specific one would move a
% variable that the rest of the clause uses.
%   GeneralSlot, SpecificSlot  a subsumption pair.
% It holds when some placeholder of the general atom holds a variable that is
% used outside that atom (in the head or in another body literal, the
% specific atom included) while the specific atom holds a different variable
% at the same placeholder. Used only, negated, by the constraint below.
general_var_unsupported(GeneralSlot, SpecificSlot) :-
    subsumption_pair(GeneralSlot, SpecificSlot),
    var_at(body, GeneralSlot, Arg, Var),
    not var_at(body, SpecificSlot, Arg, Var),
    var_used_outside_body_slot(GeneralSlot, Var).

% Positive-body same-predicate subsumption.
%
% This file rejects a general positive body literal when another positive body
% literal of the same predicate is stricter and already subsumes it. It focuses
% on same-predicate literals where the stricter literal adds an equality between
% arguments.
%
% The general atom G is redundant next to the specific atom S when a
% substitution maps G onto S and moves only variables that occur nowhere
% outside G: then S already provides a witness for those variables. Position
% matters: a variable the rest of the clause uses must sit at the same
% argument in both atoms.
% With the two atoms declared by different modes of p:
%   pruned: h(V0) :- p(V0,V1), p(V0,V0).       V1 -> V0 maps p(V0,V1) onto p(V0,V0)
%   kept:   h(V1) :- p(V0,V1), p(V0,V0).       V1 is needed by the head
%   kept:   :- p(V0,V0,V1), p(V1,V0,V2).       V1 sits at argument 2 of the
%                                              first atom and 0 of the second
% theta.lp finds exactly these substitutions between atoms of one mode: two
% atoms of a mode need recall > 1, which makes the mode movable there. This
% file therefore only compares atoms selected through different modes of the
% same predicate, which theta reduction never moves.
%
% In every rule GeneralSlot is the body slot of the candidate redundant atom
% (the "general" one) and SpecificSlot the body slot of the stricter atom.

% DEFINITION, local helper. subsumption_pair(GeneralSlot, SpecificSlot): two
% different positive body atoms that can be compared argument by argument.
%   GeneralSlot   body slot of a positive atom.
%   SpecificSlot  a body slot holding a positive atom of the same predicate
%                 and the same term shape, so both atoms have the same
%                 placeholder positions and constants, selected through a
%                 different mode.
% Both orders of a pair are derived. Used by every rule below.
subsumption_pair(GeneralSlot, SpecificSlot) :-
    positive_body_literal(GeneralSlot, GeneralMode, Pred, Arity),
    positive_body_literal(SpecificSlot, SpecificMode, Pred, Arity),
    GeneralMode != SpecificMode,
    mode_shape(GeneralMode, Shape),
    mode_shape(SpecificMode, Shape).

% ----- pruning/properties/symmetric.lp -----

% Closed-world symmetric predicate property.
%
% Python emits symmetric_pred(Pred) when binary predicate Pred is symmetric:
% Pred(X, Y) and Pred(Y, X) have same truth value. This file keeps only one
% variable orientation for selected literals and aggregate condition atoms.
%
% The swapped atom must itself be in the language. Symmetry is a fact about
% values; a template whose two arguments differ in type, direction or label
% does not admit both orders. With q(input), r(any) and friend(input,output):
%   :- q(V0), r(V1), friend(V1,V0).   legal: r binds V1, friend outputs V0
%   :- q(V0), r(V1), friend(V0,V1).   illegal: nothing binds the input V0
% so only templates with interchangeable arguments are oriented.

% CONSTRAINT. A plain atom of a symmetric predicate writes its two variables
% in ascending id order; the swapped atom means the same.
%   Section, Slot, Mode  the plain atom, in head or body and of either
%                        polarity.
%   Pred                 its predicate, symmetric and binary.
%   Mode                 also has interchangeable arguments: equal type,
%                        direction and label (interchangeable_operands).
%   Left, Right          variable ids at arguments 0 and 1.
% With friend/2 symmetric:
%   pruned: h(V0,V1) :- p(V0), p(V1), friend(V1,V0).
%   kept:   h(V0,V1) :- p(V0), p(V1), friend(V0,V1).
%   pruned: h(V0,V1) :- p(V0), p(V1), not friend(V1,V0).
:- selected(Section, Slot, Mode),
    normal_literal(Section, Slot, Mode, Pred, 2),
    symmetric_pred(Pred),
    interchangeable_operands(Mode),
    var_at(Section, Slot, 0, Left),
    var_at(Section, Slot, 1, Right),
    Left > Right.

% CONSTRAINT. The same orientation inside an aggregate: a condition atom of a
% symmetric predicate writes its two variables in ascending id order.
%   Slot             body slot of an aggregate of the single-element subset.
%   Condition, Pred  a condition occurrence and its predicate, symmetric and
%                    binary, declared with interchangeable arguments
%                    (interchangeable_condition_args).
%   Left, Right      variable ids at arguments 0 and 1 of that condition.
% With friend/2 symmetric:
%   pruned: #count{V1 : friend(V1,V0)} = V2
%   kept:   #count{V1 : friend(V0,V1)} = V2
:- selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Pred, 2),
    symmetric_pred(Pred),
    interchangeable_condition_args(Mode, Condition, 0, 1),
    aggregate_condition_arg(Slot, Condition, Pred, 0, Left),
    aggregate_condition_arg(Slot, Condition, Pred, 1, Right),
    Left > Right.

% ----- pruning/properties/total_order.lp -----

% CONSTRAINT. A total order may not be denied in both directions for two
% variables that certainly lie in its field: one direction holds there, so
% the body could never be satisfied.
%   Slot0 < Slot1  body slots of "not Pred(Left,Right)" and
%                  "not Pred(Right,Left)".
%   Pred           a total order.
%   Left, Right    two different variable ids, each bound inside field(Pred)
%                  by a positive body atom.
% With le/2 a total order on its field:
%   pruned: :- le(V0,V2), le(V1,V2), not le(V0,V1), not le(V1,V0).
%   kept:   :- le(V0,V2), le(V1,V2), not le(V0,V1).
%   kept:   :- n(V0), n(V1), not le(V0,V1), not le(V1,V0).
%           when n can reach values outside the field
:- negative_body_literal(Slot0, _, Pred, 2),
    negative_body_literal(Slot1, _, Pred, 2),
    Slot0 < Slot1,
    total_order_pred(Pred),
    var_at(body, Slot0, 0, Left),
    var_at(body, Slot0, 1, Right),
    Left != Right,
    var_at(body, Slot1, 0, Right),
    var_at(body, Slot1, 1, Left),
    covered_var(field(Pred), 0, Left),
    covered_var(field(Pred), 0, Right).

% ----- pruning/properties/transitive.lp -----

% Closed-world transitive predicate property.
%
% This file owns transitive pruning: reject explicit transitive-closure
% redundancies and negative literals contradicting such closure. Stronger
% properties such as strict_order and total_order derive transitive_pred(Pred)
% in their own files.

% CONSTRAINT. After a positive path X->Y->Z of a transitive predicate, the
% positive shortcut Pred(X,Z) is entailed and therefore redundant.
%   Slot0, Slot1  body slots of Pred(X,Y) and Pred(Y,Z), in any slot order.
%   Slot2         body slot of the shortcut Pred(X,Z); a third atom, distinct
%                 from both. Without that, p(X,Y), p(Y,Y) would read p(X,Y) as
%                 its own shortcut.
%   Pred          a transitive binary predicate.
%   X, Y, Z       variable ids.
% No slot order is required: symmetry/slots.lp sorts atoms of one mode by
% their variable tuples, which places the shortcut (V0,V2) between the two
% path atoms.
% With lt/2 transitive:
%   pruned: :- lt(V0,V1), lt(V0,V2), lt(V1,V2).     V0->V1->V2 entails V0->V2
%   kept:   :- lt(V0,V1), lt(V1,V2).
%   kept:   :- lt(V0,V1), lt(V0,V2).                 no path
% The rejected atom must not be needed by directed flow (legality/flow/
% removal.lp): otherwise the shorter clause is not in the language and this
% one has to stay.
:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    positive_body_literal(Slot2, _, Pred, 2),
    Slot2 != Slot0,
    Slot2 != Slot1,
    positive_body_capacity(Pred, Capacity), Capacity >= 2,
    transitive_pred(Pred),
    var_at(body, Slot0, 0, X),
    var_at(body, Slot0, 1, Y),
    var_at(body, Slot1, 0, Y),
    var_at(body, Slot1, 1, Z),
    var_at(body, Slot2, 0, X),
    var_at(body, Slot2, 1, Z),
    not flow_needed(Slot2).

% CONSTRAINT. After a positive path X->Y->Z of a transitive predicate,
% negating the shortcut Pred(X,Z) makes the body unsatisfiable.
%   Slot0, Slot1  body slots of the positive atoms Pred(X,Y) and Pred(Y,Z),
%                 in any slot order.
%   Slot2         body slot of "not Pred(X,Z)".
%   X, Y, Z       variable ids.
% With lt/2 transitive:
%   pruned: :- lt(V0,V1), lt(V1,V2), not lt(V0,V2).
%   kept:   :- lt(V0,V1), lt(V1,V2), not lt(V2,V0).   not the shortcut (for a
%                                                     strict order acyclic.lp
%                                                     rejects this one)
:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    negative_body_literal(Slot2, _, Pred, 2),
    transitive_pred(Pred),
    var_at(body, Slot0, 0, X),
    var_at(body, Slot0, 1, Y),
    var_at(body, Slot1, 0, Y),
    var_at(body, Slot1, 1, Z),
    var_at(body, Slot2, 0, X),
    var_at(body, Slot2, 1, Z).

% ----- pruning/properties/strict_order.lp -----

% Closed-world strict order predicate property.
%
% Python emits strict_order_pred(Pred) when binary predicate Pred behaves like a
% strict order in observed facts. A strict order is acyclic and transitive.
% Acyclic predicates already derive irreflexive and antisymmetric atoms, so this
% file does not duplicate those bridge rules.
%
% This file has no constraint of its own.

% DEFINITION, reusable property bridge. transitive_pred(Pred): Pred(X,Y) and
% Pred(Y,Z) entail Pred(X,Z).
%   Pred  signed predicate id of a binary closed predicate proved a strict
%         order.
% The shortcut checks are owned by pruning/properties/transitive.lp.
transitive_pred(Pred) :- strict_order_pred(Pred).

% ----- pruning/properties/total_order.lp -----

% DEFINITION, reusable property bridge. transitive_pred(Pred): Pred(X,Y) and
% Pred(Y,Z) entail Pred(X,Z).
%   Pred  as above.
% The shortcut checks are owned by pruning/properties/transitive.lp.
transitive_pred(Pred) :- total_order_pred(Pred).

% ----- pruning/properties/universal.lp -----

% A universal predicate holds for every tuple of the product of its argument
% values (see domains.lp). A positive literal is redundant when other positive
% literals bind every argument inside that product; its negation is then
% impossible.
%   same(a,a). same(a,b). same(b,a). same(b,b). n(a). n(b). n(c).
%   h(X) :- same(X,Y), n(Y), not same(Y,X).   pruned: X, Y come from same's product
%   h(X) :- n(X), n(Y), not same(X,Y).         kept: c lies outside the product

% CONSTRAINT. A positive body atom of a universal predicate is redundant when
% every one of its arguments is a variable that a different positive atom
% binds inside the predicate's product: the atom is then always true.
%   Slot  body slot of the positive atom.
%   Pred  its predicate, universal.
% With the facts of the file header and k(a). k(b). as another predicate
% whose values lie inside the product:
%   pruned: h(V0) :- k(V0), k(V1), same(V0,V1).
%   kept:   h(V0) :- same(V0,V1).               nothing else binds V0 and V1
%   kept:   h(V0) :- n(V0), n(V1), same(V0,V1).   n reaches c; same filters it
% The rejected atom must not be needed by directed flow (legality/flow/
% removal.lp): otherwise the shorter clause is not in the language and this
% one has to stay.
:- positive_body_literal(Slot, _, Pred, _),
    universal_pred(Pred),
    not domain_literal_uncovered_elsewhere(universal(Pred), Slot),
    not flow_needed(Slot).

% ----- legality/flow/removal.lp -----

% DEFINITION, reusable. flow_needed(Slot): removing the positive body atom at
% Slot may leave the clause without a producer or binder it needs.
%   Slot  body slot of a positive plain atom.
% Consumed, negated, by every pruning that rejects a clause for containing a
% redundant positive atom: pruning/properties/implies.lp, universal.lp,
% reflexive.lp, project_implies.lp, transitive.lp, inverse.lp and
% subsumption.lp. One definition keeps "this atom may be dropped" in a single
% place.
% Case 1: the atom outputs a variable used elsewhere that no free atom
% outputs.
%   Mode, Arg  its template and an output placeholder.
%   Var        variable id written there and used outside the atom.
flow_needed(Slot) :-
    positive_body_literal(Slot, Mode, _, _),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var),
    var_used_outside_body_slot(Slot, Var),
    not produced_without(Slot, Var).

% DEFINITION, reusable. Same predicate. Case 2: the atom binds, at an "any"
% placeholder, a variable used elsewhere that nothing else binds
% unconditionally.
flow_needed(Slot) :-
    positive_body_literal(Slot, Mode, _, _),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Slot, Arg, Var),
    var_used_outside_body_slot(Slot, Var),
    not bound_without(Slot, Var).

% ----- representation/tuples.lp -----

% DEFINITION, reusable. var_used_outside_body_slot(Slot, Var): Var occurs
% somewhere other than in body Slot.
%   Slot  any body slot, occupied or not; the slot being excluded.
%   Var   variable id with an occurrence outside that slot.
% Shared by pruning/policies/aggregates.lp (an aggregate result must be used)
% and pruning/properties/subsumption.lp (a removed literal must not move a
% variable the rest of the clause needs).
% Case 1: any head occurrence.
var_used_outside_body_slot(Slot, Var) :- body_slot(Slot), var_at(head, _, _, Var).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: an occurrence in a different body slot, whatever literal holds it.
var_used_outside_body_slot(Slot, Var) :-
    body_slot(Slot),
    var_at(body, OtherSlot, _, Var),
    OtherSlot != Slot.

% ----- legality/flow/removal.lp -----

% DEFINITION, local helper. bound_without(Slot, Var): Var stays bound when the
% atom at Slot is removed.
%   Slot  body slot of the atom whose removal is being considered.
%   Var   variable id still available to feed inputs.
% Used only, negated, by flow_needed below.
% Case 1: another atom outputs it unconditionally.
bound_without(Slot, Var) :- produced_without(Slot, Var).

% DEFINITION, local helper. Same predicate. Case 2: another atom of a free
% binding mode holds it at an "any" placeholder.
bound_without(Slot, Var) :-
    positive_body_literal(Slot, _, _, _),
    selected(body, Other, Mode),
    Other != Slot,
    free_binding_mode(Mode),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Other, Arg, Var),
    not pooled_body_missing_var(Other, Var).

% DEFINITION, local helper. Same predicate. Case 3: it is a head input, bound
% from the start.
bound_without(Slot, Var) :-
    positive_body_literal(Slot, _, _, _),
    head_input_var(Var).

% DEFINITION, local helper. produced_without(Slot, Var): some atom other than
% the one at Slot outputs Var unconditionally.
%   Slot  body slot of the atom whose removal is being considered.
%   Var   variable id at an output placeholder of a different body atom of a
%         free binding mode, grounded in every binding alternative.
% Used by bound_without and flow_needed below.
produced_without(Slot, Var) :-
    positive_body_literal(Slot, _, _, _),
    selected(body, Other, Mode),
    Other != Slot,
    free_binding_mode(Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Other, Arg, Var),
    not pooled_body_missing_var(Other, Var).

% DEFINITION, local helper. free_binding_mode(Mode): literals of Mode supply
% their variables unconditionally.
%   Mode  id of a positive plain atom template without input placeholders.
% Such a literal is ready whatever else the clause contains, so what it
% supplies does not depend on the atom being removed. Used only by the two
% views below.
free_binding_mode(Mode) :- binding_mode(Mode), not mode_needs_input(Mode).

% Whether a positive body atom can be removed without breaking directed flow.
%
% Several prunings reject a clause because one of its positive atoms is
% redundant: the clause without that atom means the same and is enumerated on
% its own. That only holds if the shorter clause is in the language. With
% directed modes the redundant atom may be the only producer of a variable:
%   #modeb(1,node(var(t,output))).  #modeb(1,red(var(t,input))).
%   h(V0) :- node(V0), red(V0).     red implies node, so node(V0) is redundant
%   h(V0) :- red(V0).               illegal: nothing binds the input of red
% Rejecting the first clause would leave "h is what is red" unlearnable.
%
% flow_needed(Slot) is a sufficient test, not the exact fixed point without
% the atom: it accepts a removal only when another atom that needs no input
% supplies each variable at least as strongly. When in doubt the atom counts
% as needed and the redundant clause is kept, which is always sound.
%
% This file has no constraint of its own.

% DEFINITION, local helper. mode_needs_input(Mode): literals of Mode wait for
% some input before they supply anything.
%   Mode  id of a template with at least one placeholder declared input.
% Used only, negated, by free_binding_mode below.
mode_needs_input(Mode) :- mode_arg_direction(Mode, _, input).

% ----- legality/flow/seeds.lp -----

% Initial flow bindings: head inputs, aggregate results and undirected
% positive any positions of normal body atoms. A head input is bound for body
% inputs and satisfies only a coincident head output (requirements.lp); it
% never produces a body output. Only a positive normal atom binds: comparison,
% arithmetic, aggregate and conditional positions never bind a global variable.
% ASP grounding safety is checked separately in legality/asp_safety.lp.

% DEFINITION, reusable. binding_mode(Mode): literals of this mode can supply
% variable values.
%   Mode  id of a plain atom template without default negation.
% Shared by the seed below and by legality/flow/closure.lp, so that "what may
% bind" is decided once.
binding_mode(Mode) :- normal_mode(Mode), positive_mode(Mode).

% DEFINITION, reusable. head_input_var(Var): the head receives Var as input.
%   Var  variable id at a placeholder declared input of a non-conditional head
%        literal. With target(input,output), "target(V0,V1)" gives V0.
% Shared by the seed below and by legality/flow/requirements.lp, where a head
% input also satisfies an output position of the head.
head_input_var(Var) :-
    selected(head, Slot, Mode),
    not conditional_mode(Mode),
    mode_arg_direction(Mode, Arg, input),
    var_at(head, Slot, Arg, Var).

% ----- pruning/properties/domains.lp -----

% DEFINITION, reusable. domain_literal_uncovered_elsewhere(Domain, Slot): some
% argument of the body literal at Slot is not covered by another literal.
%   Arguments as in domain_literal_uncovered/2.
% Consumed, negated, by pruning/properties/universal.lp to decide whether a
% positive atom is redundant.
domain_literal_uncovered_elsewhere(Domain, Slot) :-
    domain_member(Domain, Pred),
    normal_literal(body, Slot, _, Pred, Arity),
    Position = 0..Arity-1,
    not domain_position_covered_elsewhere(Domain, Slot, Position).

% DEFINITION, local helper. domain_position_covered_elsewhere(Domain, Slot,
% Position): the same, but the covering positive atom is a different literal.
%   Arguments as above; Cover (body variable) is the slot of the covering
%   atom and differs from Slot.
% Needed when the inspected literal is itself positive: it must not justify
% its own removal. Used only, negated, by domain_literal_uncovered_elsewhere.
domain_position_covered_elsewhere(Domain, Slot, Position) :-
    var_at(body, Slot, Position, Var),
    covered_var(Domain, Position, Var, Cover),
    Cover != Slot.

% ----- pruning/properties/universal.lp -----

% CONSTRAINT. A negated body atom of a universal predicate is impossible when
% every one of its arguments is a variable that a positive atom binds inside
% the predicate's product.
%   Slot  body slot of the negated atom.
%   Pred  its predicate, universal.
%   pruned and kept: see the two examples in the file header.
:- negative_body_literal(Slot, _, Pred, _),
    universal_pred(Pred),
    not domain_literal_uncovered(universal(Pred), Slot).

% ----- pruning/properties/domains.lp -----

% A constant or an uncovered variable at any position blocks the pruning.
% DEFINITION, reusable. domain_literal_uncovered(Domain, Slot): the body
% literal at Slot may denote a tuple outside Domain.
%   Domain  a domain with member predicates.
%   Slot    body slot of a plain atom, of either polarity, of a member
%           predicate, with some argument position that is not covered.
% Consumed, negated, by pruning/properties/complement.lp, partition.lp and
% universal.lp: their prunings apply only when every argument is covered.
domain_literal_uncovered(Domain, Slot) :-
    domain_member(Domain, Pred),
    normal_literal(body, Slot, _, Pred, Arity),
    Position = 0..Arity-1,
    not domain_position_covered(Domain, Slot, Position).

% Domain-relative properties hold only on the finite domain Python checked.
%
% Python emits domain_cover(Domain, Position, Pred, Arg) when every value of
% closed predicate Pred at argument Arg lies inside position Position of Domain.
% A variable bound there by a positive body literal therefore ranges over
% checked values. A variable bound only elsewhere (arithmetic, an aggregate
% result, another predicate) may take values the property says nothing about.
%
%   le(1,1). le(2,2). le(1,2). n(1..3).   reflexive on field {1,2}
%   h(X) :- le(X,Y), not le(X,X).          pruned: X comes from le's field
%   h(X) :- n(X), not le(X,X).             kept: X = 3 lies outside the field
%
% This file has no constraint of its own. Domain is one of the terms field(P),
% universal(P), complement(P,Q) or partition(Group).

% DEFINITION, local helper. domain_member(Domain, Pred): Pred is one of the
% predicates whose property is relative to Domain.
%   Domain  complement(Pred0, Pred1), partition(Part) or universal(Pred).
%   Pred    signed predicate id of a member. field(P) domains have no member
%           facts: reflexive.lp and total_order.lp query covered_var directly.
% Used only by the two domain_literal_uncovered views at the end.
% Case 1: the first predicate of a complement pair.
domain_member(complement(Pred0, Pred1), Pred0) :- complement_pred(Pred0, Pred1).
% DEFINITION, local helper. Same predicate. Case 2: the second predicate of a
% complement pair.
domain_member(complement(Pred0, Pred1), Pred1) :- complement_pred(Pred0, Pred1).
% DEFINITION, local helper. Same predicate. Case 3: each predicate of a
% partition.
domain_member(partition(Part), Pred) :- partition_pred(Part, Pred).
% DEFINITION, local helper. Same predicate. Case 4: a universal predicate.
domain_member(universal(Pred), Pred) :- universal_pred(Pred).

% DEFINITION, local helper. domain_position_covered(Domain, Slot, Position):
% argument Position of the body literal at Slot holds a variable whose values
% lie inside the same position of Domain.
%   Domain    the domain term.
%   Slot      body slot of the literal under inspection.
%   Position  one of its argument positions; it is also the domain position
%             consulted.
% Used only, negated, by domain_literal_uncovered below.
domain_position_covered(Domain, Slot, Position) :-
    var_at(body, Slot, Position, Var),
    covered_var(Domain, Position, Var).

% DEFINITION, reusable. covered_var(Domain, Position, Var): some positive body
% atom binds Var inside that position of Domain.
%   Arguments as in covered_var/4, without the Slot.
% Shared by domain_position_covered below and by
% pruning/properties/reflexive.lp and total_order.lp.
covered_var(Domain, Position, Var) :- covered_var(Domain, Position, Var, _).

% DEFINITION, reusable. covered_var(Domain, Position, Var, Slot): the positive
% body atom at Slot binds Var to values inside one position of Domain.
%   Domain    the domain term.
%   Position  position of the domain whose values contain those of the
%             binding argument.
%   Var       variable id written at that argument.
%   Slot      body slot of the positive atom that binds it.
% The Slot is kept for consumers that must exclude a literal covering itself:
% pruning/properties/reflexive.lp and domain_position_covered_elsewhere below.
covered_var(Domain, Position, Var, Slot) :-
    domain_cover(Domain, Position, Pred, Arg),
    positive_body_literal(Slot, _, Pred, _),
    var_at(body, Slot, Arg, Var).

% ----- pruning/redundancy/aggregates.lp -----

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

% ----- representation/aggregates.lp -----

% DEFINITION, reusable. aggregate_result_var(Slot, Variable): the value the
% aggregate at body Slot is equated to.
%   Slot      body slot of an aggregate of the single-element subset.
%   Variable  variable id of the result: V2 in "#count{V0 : p(V0)} = V2".
% Shared by representation/variables.lp, legality/asp_safety.lp and
% legality/flow/seeds.lp (the result is a produced, safe output),
% pruning/policies/aggregates.lp and pruning/redundancy/aggregates.lp.
aggregate_result_var(Slot, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_result_arg(Mode, Position),
    var_at(body, Slot, Position, Variable).

% ----- pruning/redundancy/aggregates.lp -----

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
    var_at(body, Slot0, Arg, Var),
    not var_at(body, Slot1, Arg, Var).

% ----- representation/aggregates.lp -----

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

% DEFINITION, reusable. aggregate_internal_arg(Slot, Position), case 3: every
% element placeholder is interior, which extends the view from the
% single-element subset to all body aggregates.
aggregate_internal_arg(Slot, Position) :- aggregate_element_arg(Slot, _, Position).

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

% ----- pruning/redundancy/aggregates.lp -----

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

% ----- representation/aggregates.lp -----

% DEFINITION, reusable. aggregate_tuple_var(Slot, Variable): Variable is some
% tuple term of the aggregate at body Slot.
%   Slot      body slot of an aggregate of the single-element subset.
%   Variable  variable id at any tuple position.
% Drops the position for consumers that only ask about membership:
% representation/variables.lp, legality/aggregates.lp, symmetry/aggregates.lp
% and pruning/redundancy/aggregates.lp.
aggregate_tuple_var(Slot, Variable) :- aggregate_tuple_binding(Slot, _, Variable).

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

% ----- pruning/redundancy/arithmetic.lp -----

% CONSTRAINT. The same computation may not be given two result variables:
% both are necessarily equal, so the clause is the one that computes it once.
%   Slot0, Slot1      adjacent arithmetic literals with identical operands.
%   Result0, Result1  their result variable ids, which differ.
%   pruned: ..., V0+V1=V2, V0+V1=V3, r(V2,V3).
%   kept:   ..., V0+V1=V2, r(V2,V2).
:- same_arithmetic_inputs(Slot0, Slot1),
    arithmetic_result(Slot0, Result0),
    arithmetic_result(Slot1, Result1),
    Result0 != Result1.

% DEFINITION, local helper. same_arithmetic_inputs(Slot0, Slot1): two adjacent
% arithmetic literals of the same mode have the same operands, so they
% compute the same value.
%   Slot0, Slot1  adjacent body slots, as above.
% Used only by the constraint below.
same_arithmetic_inputs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    arithmetic_mode(Mode),
    Slot1 = Slot0 + 1,
    not arithmetic_input_differs(Slot0, Slot1).

% Reject repeated computations and the existing removable common-factor form.
% Equal modes are tuple-sorted, so identical inputs occupy adjacent slots.
% Different result ids are syntactic bindings, not a proof of unequal values.

% DEFINITION, local helper. arithmetic_input_differs(Slot0, Slot1): two
% adjacent arithmetic literals of the same mode differ in some operand.
%   Slot0  body slot of an arithmetic literal.
%   Slot1  the next slot (Slot0 + 1), holding the same mode.
% Operands are compared side by side: left with left, right with right. Used
% only, negated, by same_arithmetic_inputs below.
arithmetic_input_differs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    arithmetic_mode(Mode),
    Slot1 = Slot0 + 1,
    arithmetic_operand(Slot0, Side, Operand),
    not arithmetic_operand(Slot1, Side, Operand).

% ----- representation/operators.lp -----

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

% ----- pruning/redundancy/arithmetic.lp -----

% CONSTRAINT. Two doublings may not share one result: Left+Left = Result and
% Right+Right = Result force Left = Right, which the enumerator expresses by
% writing a single variable id instead.
%   Mode    the addition template both literals use.
%   Left    the smaller of the two doubled variable ids.
%   Right   the other one; two different doubled variables are necessarily
%           two literals.
%   Result  the result variable id shared by both.
% Both doubled variables must be grounded by positive plain body atoms.
%   pruned: :- n(V0), n(V1), V0+V0=V2, V1+V1=V2.
%   kept:   :- n(V0), n(V1), V0+V0=V2, V1+V1=V3, r(V2,V3).   different results
:- doubles_to(Mode, Left, Result),
    doubles_to(Mode, Right, Result),
    Left < Right,
    normal_positive_body_var(Left),
    normal_positive_body_var(Right).

% ----- legality/asp_safety.lp -----

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

% ----- representation/arguments.lp -----

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

% ----- pruning/redundancy/arithmetic.lp -----

% DEFINITION, local helper. doubles_to(Mode, Var, Result): the body states
% Var + Var = Result through the addition template Mode.
%   Mode    id of the addition template.
%   Var     the variable id used as both operands.
%   Result  the result variable id.
% The slot is dropped on purpose: the constraint below only needs the
% variables, and keeping slots would ground it once per pair of slots. Used
% only by that constraint.
doubles_to(Mode, Var, Result) :-
    selected(body, Slot, Mode),
    add_mode(Mode),
    arithmetic_operand(Slot, left, Var),
    arithmetic_operand(Slot, right, Var),
    arithmetic_result(Slot, Result).

% ----- pruning/redundancy/comparisons.lp -----

% Reject comparisons entailed by other selected comparisons.
% Optional canonical strict components. Python proves the restricted family:
% plain heads/atoms, bare strict numeric input comparisons and arithmetic, no
% conditions or <=/!=/= templates whose recall-dependent pruning could change
% after removal. These skeletons equate X<Y with Y>X before full models return.
% Only repeated selected occurrences are excluded: either single mode remains.
canonical_strict_literal(Slot, Left, Right) :-
    canonical_components, selected(body, Slot, Mode), canonical_strict_mode(Mode, 0),
    var_at(body, Slot, 0, Left), var_at(body, Slot, 1, Right).
canonical_strict_literal(Slot, Right, Left) :-
    canonical_components, selected(body, Slot, Mode), canonical_strict_mode(Mode, 1),
    var_at(body, Slot, 0, Left), var_at(body, Slot, 1, Right).
:- canonical_strict_literal(Slot0, Left, Right),
    canonical_strict_literal(Slot1, Left, Right), Slot0 < Slot1.

% CONSTRAINT. "Left <= Right" is redundant next to "Left < Right".
%   Left, Right  variable ids.
%   pruned: ..., V0 < V1, V0 <= V1.
%   kept:   ..., V0 < V1.
:- selected_lt(Left, Right), selected_leq(Left, Right).

% CONSTRAINT. "Left != Right" is redundant next to "Left < Right".
%   Left, Right  variable ids.
%   pruned: ..., V0 < V1, V0 != V1.
%   kept:   ..., V0 < V1.
:- selected_lt(Left, Right), selected_neq(Left, Right).

% CONSTRAINT. "Left <= Right, Left != Right" is rejected when the language
% can say "Left < Right" directly.
%   Left, Right  the variable ids of the pair.
%   pruned: ..., V0 <= V1, V0 != V1.     when a usable "<" or ">" mode exists
%   kept:   ..., V0 < V1.
%   kept:   ..., V0 <= V1, V0 != V1.     when no strict mode admits V0 and V1
:- strict_mode_for(_, Left, Right).

% Transitive shortcuts use selected edges; inferred closure must not masquerade
% as selected literals.
%
% X<=Y, X!=Y equals X<Y only when that X<Y is in the language: a < mode (or a
% > mode read in reverse) whose declared types admit both variables and whose
% recall is not exhausted. With <= and != on type t and < only on type u,
% h(X) :- p(X,Y), X<=Y, X!=Y has no shorter equivalent and stays.
%
% In the examples "..." stands for body atoms that ground the variables.

% DEFINITION, local helper. strict_mode_for(Mode, Left, Right): the pair
% "Left <= Right, Left != Right" written in the body could be replaced by one
% literal of the strict comparison template Mode.
%   Mode   id of a declared simple strict comparison.
%   Left   variable id on the smaller side of the selected "<=".
%   Right  variable id on the greater side of the selected "<=".
% Used only by the third constraint below.
% Case 1: Mode is a "<" template. Left would fill its placeholder 0 and Right
% its placeholder 1; neither may have a conflicting type, and the template
% must still have recall left.
strict_mode_for(Mode, Left, Right) :-
    comparison_operator(Mode, lt),
    selected_leq(Left, Right), selected_neq(Left, Right),
    not comparison_type_conflict(Mode, 0, Left),
    not comparison_type_conflict(Mode, 1, Right),
    not comparison_recall_full(Mode).

% DEFINITION, local helper. Same predicate. Case 2: Mode is a ">" template,
% read in reverse: "Right > Left". Right would fill placeholder 0 and Left
% placeholder 1.
strict_mode_for(Mode, Left, Right) :-
    comparison_operator(Mode, gt),
    selected_leq(Left, Right), selected_neq(Left, Right),
    not comparison_type_conflict(Mode, 1, Left),
    not comparison_type_conflict(Mode, 0, Right),
    not comparison_recall_full(Mode).

% DEFINITION, local helper. comparison_type_conflict(Mode, Position, Var):
% variable Var cannot be written at that placeholder of comparison Mode.
%   Mode      id of a simple strict comparison template.
%   Position  one of its placeholders, 0 or 1, with a declared type.
%   Var       a variable id that occurs somewhere in the clause at a
%             placeholder of a different declared type.
% Used only, negated, by strict_mode_for above.
comparison_type_conflict(Mode, Position, Var) :-
    comparison_operator(Mode, (lt; gt)),
    mode_arg_type(Mode, Position, Type),
    var_at(Section, Slot, Arg, Var),
    arg_type(Section, Slot, Arg, Other),
    Other != Type.

% DEFINITION, local helper. comparison_recall_full(Mode): no further literal
% of that comparison declaration fits in the clause.
%   Mode  id of a simple strict comparison template whose recall group
%         already has as many selected literals as its recall allows.
% Used only, negated, by strict_mode_for above.
comparison_recall_full(Mode) :-
    comparison_operator(Mode, (lt; gt)),
    recall_group(Mode, Group),
    selected_count(Group, Count),
    group_recall(Group, Recall),
    Count >= Recall.

% ----- legality/recall.lp -----

% DEFINITION, reusable. selected_count(Group, Count): how many literals of one
% mode declaration the clause selects.
%   Group  id of the declaration's recall group.
%   Count  number of selected slots, in head and body, whose mode belongs to
%          the group; 0 when none is selected.
% Shared by the constraint below and pruning/redundancy/comparisons.lp.
selected_count(Group, Count) :-
    group_recall(Group, Recall),
    Count = #count{Section, Slot, Mode : selected(Section, Slot, Mode), recall_group(Mode, Group)}.

% DEFINITION, reusable. group_recall(Group, Recall): the recall cap of one
% mode declaration.
%   Group   id shared by every mode expanded from the same declaration (one
%           declaration can expand into several concrete modes).
%   Recall  the smallest mode_recall among those modes.
% Shared by selected_count and the constraint below, and by
% pruning/redundancy/comparisons.lp, which asks whether a "<" declaration
% still has room.
group_recall(Group, Recall) :-
    recall_group(_, Group),
    Recall = #min{ModeRecall : recall_group(Mode, Group), mode_recall(Mode, ModeRecall)}.

% ----- pruning/redundancy/comparisons.lp -----

% The ten constraints below remove a comparison between Left and Right that
% follows from two other selected comparisons through Middle. They join
% selected literals only, never inferred_lt. Left, Middle and Right are
% variable ids in all of them.

% CONSTRAINT. Left < Middle and Middle < Right entail Left < Right.
%   pruned: ..., V0 < V2, V0 < V1, V1 < V2.
%   kept:   ..., V0 < V1, V1 < V2.
:- selected_lt(Left, Right), selected_lt(Left, Middle), selected_lt(Middle, Right).

% CONSTRAINT. Left < Middle and Middle <= Right entail Left < Right.
%   pruned: ..., V0 < V2, V0 < V1, V1 <= V2.
%   kept:   ..., V0 < V1, V1 <= V2.
:- selected_lt(Left, Right), selected_lt(Left, Middle), selected_leq(Middle, Right).

% CONSTRAINT. Left <= Middle and Middle < Right entail Left < Right.
%   pruned: ..., V0 < V2, V0 <= V1, V1 < V2.
%   kept:   ..., V0 <= V1, V1 < V2.
:- selected_lt(Left, Right), selected_leq(Left, Middle), selected_lt(Middle, Right).

% CONSTRAINT. Left < Middle and Middle < Right entail Left <= Right.
%   pruned: ..., V0 <= V2, V0 < V1, V1 < V2.
%   kept:   ..., V0 < V1, V1 < V2.
:- selected_leq(Left, Right), selected_lt(Left, Middle), selected_lt(Middle, Right).

% CONSTRAINT. Left < Middle and Middle <= Right entail Left <= Right.
%   pruned: ..., V0 <= V2, V0 < V1, V1 <= V2.
%   kept:   ..., V0 < V1, V1 <= V2.
:- selected_leq(Left, Right), selected_lt(Left, Middle), selected_leq(Middle, Right).

% CONSTRAINT. Left <= Middle and Middle < Right entail Left <= Right.
%   pruned: ..., V0 <= V2, V0 <= V1, V1 < V2.
%   kept:   ..., V0 <= V1, V1 < V2.
:- selected_leq(Left, Right), selected_leq(Left, Middle), selected_lt(Middle, Right).

% CONSTRAINT. Left <= Middle and Middle <= Right entail Left <= Right.
%   pruned: ..., V0 <= V2, V0 <= V1, V1 <= V2.
%   kept:   ..., V0 <= V1, V1 <= V2.
:- selected_leq(Left, Right), selected_leq(Left, Middle), selected_leq(Middle, Right).

% CONSTRAINT. Left < Middle and Middle < Right entail Left != Right.
%   pruned: ..., V0 != V2, V0 < V1, V1 < V2.
%   kept:   ..., V0 < V1, V1 < V2.
:- selected_neq(Left, Right), selected_lt(Left, Middle), selected_lt(Middle, Right).

% CONSTRAINT. Left < Middle and Middle <= Right entail Left != Right.
%   pruned: ..., V0 != V2, V0 < V1, V1 <= V2.
%   kept:   ..., V0 < V1, V1 <= V2.
:- selected_neq(Left, Right), selected_lt(Left, Middle), selected_leq(Middle, Right).

% CONSTRAINT. Left <= Middle and Middle < Right entail Left != Right.
%   pruned: ..., V0 != V2, V0 <= V1, V1 < V2.
%   kept:   ..., V0 <= V1, V1 < V2.
%   kept:   ..., V0 != V2, V0 <= V1, V1 <= V2.   two "<=" do not entail "!="
:- selected_neq(Left, Right), selected_leq(Left, Middle), selected_lt(Middle, Right).

% ----- representation/operators.lp -----

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

% ----- pruning/redundancy/conditions.lp -----

% CONSTRAINT. A condition repeated with identical variables is rejected when
% the language also declares the same conditional without that repeat.
%   Section, Slot  the conditional literal.
%   Left, Right    the duplicated conditions; Right is the removable one.
%   Mode           the selected template, which has a declared variant
%                  without condition Right (conditional_shorter_mode).
%   pruned: :- p(V0) : q(V0), q(V0).     when "p : q" is also in the language
%   kept:   :- p(V0) : q(V0).
%   kept:   :- p(V0) : q(V0), q(V1).     different variables
%   kept:   :- p(V0) : q(V0), q(V0).     when the bias declares only the
%                                        two-condition attachment
:- same_condition_vars(Section, Slot, Left, Right),
    selected(Section, Slot, Mode),
    conditional_shorter_mode(Mode, Right).

% Reject repeated conditions with identical template variant and bindings, but
% only when the template without the repeat is itself in the language. An exact
% attachment such as e(X,X):d(X),d(X) has no shorter declared form, so it stays.

% DEFINITION, local helper. same_condition_vars(Section, Slot, Left, Right):
% two conditions of one conditional literal are the same condition written
% twice.
%   Section, Slot  the selected conditional literal.
%   Left           index of a condition.
%   Right          index of a later condition (Left < Right) of the same
%                  variant: same predicate, polarity, term shape and
%                  placeholder types, directions and labels.
% It holds when every argument of Left holds the same variable as the matching
% argument of Right: the two #count aggregates compare the number of arguments
% with the number of arguments that agree. Used only by the constraint below.
same_condition_vars(Section, Slot, Left, Right) :-
    selected(Section, Slot, Mode),
    conditional_condition_variant(Mode, Left, Variant),
    conditional_condition_variant(Mode, Right, Variant),
    Left < Right,
    Count = #count { Relative : conditional_condition_arg(Mode, Left, Relative, _) },
    Count = #count {
        Relative :
        conditional_condition_arg(Mode, Left, Relative, LeftArg),
        conditional_condition_arg(Mode, Right, Relative, RightArg),
        var_at(Section, Slot, LeftArg, Var),
        var_at(Section, Slot, RightArg, Var)
    }.

% ----- pruning/redundancy/literals.lp -----

% CONSTRAINT. A plain atom may not be written twice in the same section.
%   Section0, Slot0, Section1, Slot1  the duplicated pair.
%   pruned: h(V0) :- p(V0,V1), p(V0,V1).
%   pruned: h(V0) :- q(V0), not p(V0), not p(V0).
%   pruned: p(V0);p(V0) :- q(V0).               a duplicate in the head
%   kept:   h(V0) :- p(V0,V1), p(V1,V0).
:- same_normal_literal(Section0, Slot0, Section1, Slot1).

% Reject repeated literals of the same polarity within a section.
% Equal modes are contiguous and tuple-sorted, so adjacent checks cover repeats;
% different normal modes still require cross-slot comparisons. Opposite body
% polarities and a head/body match are handled by tautologies.lp.

% DEFINITION, local helper. same_normal_literal(Section0, Slot0, Section1,
% Slot1): two plain atoms of one section are the same literal written twice.
%   Section0, Slot0  the first occurrence.
%   Section1, Slot1  the second occurrence; always the same section as the
%                    first, and a later slot.
% "Same literal" is same predicate, same polarity, same term shape and same
% variables. Used only by the constraint below.
% Case 1: two positive atoms selected through different modes of the same
% predicate, for example one declaration with var(t,input) and another with
% var(t,output). They can sit at any two slots of the section.
same_normal_literal(Section, Slot0, Section, Slot1) :-
    positive_normal_literal(Section, Slot0, Mode0, Pred, Arity),
    positive_normal_literal(Section, Slot1, Mode1, Pred, Arity),
    Slot0 < Slot1,
    Mode0 != Mode1,
    same_term_bindings(Section, Slot0, Section, Slot1).

% DEFINITION, local helper. Same predicate. Case 2: two default-negated body
% atoms selected through different modes of the same predicate.
same_normal_literal(body, Slot0, body, Slot1) :-
    negative_body_literal(Slot0, Mode0, Pred, Arity),
    negative_body_literal(Slot1, Mode1, Pred, Arity),
    Slot0 < Slot1,
    Mode0 != Mode1,
    same_term_bindings(body, Slot0, body, Slot1).

% DEFINITION, local helper. Same predicate. Case 3: two atoms of the same
% mode, hence the same polarity. Equal modes are contiguous and sorted
% (symmetry/slots.lp), so a repeat can only sit in the next slot.
same_normal_literal(Section, Slot0, Section, Slot1) :-
    normal_literal(Section, Slot0, Mode, Pred, Arity),
    normal_literal(Section, Slot1, Mode, Pred, Arity),
    Slot1 = Slot0 + 1,
    same_term_bindings(Section, Slot0, Section, Slot1).

% CONSTRAINT. A comparison, arithmetic, aggregate or conditional literal may
% not be written twice in the body.
%   Section0, Slot0, Section1, Slot1  the duplicated pair (always in the body).
%   pruned: :- p(V0,V1), V0 < V1, V0 < V1.
%   pruned: :- p(V0,V1), V0+V1=V2, V0+V1=V2, r(V2).
%   kept:   :- p(V0,V1), V0 < V1.
:- same_mode_literal(Section0, Slot0, Section1, Slot1).

% DEFINITION, local helper. same_mode_literal(body, Slot0, body, Slot1): two
% adjacent body literals of the same non-plain mode are identical.
%   body   the section; only body literals are compared.
%   Slot0  body slot of a comparison, arithmetic, aggregate, conditional or
%          boolean literal.
%   Slot1  the next slot (Slot0 + 1), holding the same mode with the same
%          variables at every placeholder.
% Used only by the constraint below.
same_mode_literal(body, Slot0, body, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    not normal_mode(Mode),
    Slot1 = Slot0 + 1,
    same_term_bindings(body, Slot0, body, Slot1).

% ----- pruning/redundancy/numeric.lp -----

% A sign-known addition already entails the selected operand/result comparison:
% with Rt > 0, R = L + Rt entails L < R and L <= R; with Rt >= 0 it entails
% L <= R. Signs come from inference/numeric.lp.
%
% In the examples n/1 is a closed predicate whose argument is proved > 0 and
% z/1 one whose argument is proved >= 0.

% CONSTRAINT. With Right > 0, "Left < Result" repeats what the addition says.
%   Slot    body slot of "Left + Right = Result".
%   Left    left operand.
%   Right   right operand, proved > 0.
%   Result  the sum, explicitly compared as Left < Result.
%   pruned: n(V1), V0+V1=V2, V0 < V2.
%   kept:   n(V1), V0+V1=V2.
%   kept:   V0+V1=V2, V0 < V2 without sign evidence for V1: it is informative
:- addition(Slot, Left, Right, Result),
    positive_value(Right),
    selected_lt(Left, Result).

% CONSTRAINT. The mirror image: with Left > 0, "Right < Result" is entailed.
%   Left    left operand, proved > 0.
%   Result  the sum, explicitly compared as Right < Result.
%   pruned: n(V0), V0+V1=V2, V1 < V2.
%   kept:   n(V0), V0+V1=V2.
:- addition(Slot, Left, Right, Result),
    positive_value(Left),
    selected_lt(Right, Result).

% CONSTRAINT. With Right >= 0, "Left <= Result" is entailed.
%   Right   right operand, proved >= 0.
%   Result  the sum, explicitly compared as Left <= Result.
%   pruned: z(V1), V0+V1=V2, V0 <= V2.
%   kept:   z(V1), V0+V1=V2, V0 < V2.       strict: V1 could be 0
:- addition(Slot, Left, Right, Result),
    nonnegative_value(Right),
    selected_leq(Left, Result).

% CONSTRAINT. The mirror image: with Left >= 0, "Right <= Result" is entailed.
%   Left    left operand, proved >= 0.
%   Result  the sum, explicitly compared as Right <= Result.
%   pruned: z(V0), V0+V1=V2, V1 <= V2.
%   kept:   z(V0), V0+V1=V2, V1 < V2.
:- addition(Slot, Left, Right, Result),
    nonnegative_value(Left),
    selected_leq(Right, Result).

% ----- inference/numeric.lp -----

% DEFINITION, reusable. nonnegative_value(Var): every value Var can take is an
% integer >= 0.
%   Var  variable id.
% Shared by pruning/contradictions/numeric.lp and pruning/redundancy/numeric.lp.
% Case 1: a positive body atom grounds Var at an argument proved >= 0.
nonnegative_value(Var) :-
    positive_body_literal(Slot, _, Pred, _),
    nonnegative_arg(Pred, Arg),
    var_at(body, Slot, Arg, Var).

% DEFINITION, reusable. Same predicate. Case 2: > 0 entails >= 0.
nonnegative_value(Var) :- positive_value(Var).

% Derive sign and strict value order from selected arithmetic and the
% per-argument evidence Python proves with Clingo. positive_arg(Pred, Arg) and
% nonnegative_arg(Pred, Arg) hold when every value that argument of a closed
% predicate takes, in every model of every context, is an integer > 0 or >= 0.
% Only a positive body literal grounds its variable to such a value: a head
% atom, a negated literal or a learned predicate says nothing about it.
% inferred_lt is a transitive closure; selected_lt continues to mean an
% explicit comparison literal.

% DEFINITION, reusable. positive_value(Var): every value Var can take in the
% candidate clause is an integer > 0.
%   Var  variable id. The claim is about its ground values, not about the id.
% Shared by the rules below, pruning/contradictions/numeric.lp (impossible
% orders) and pruning/redundancy/numeric.lp (entailed comparisons).
% Case 1: a positive body atom grounds Var at an argument proved > 0. With
% positive_arg(size,1), "size(V0,V1)" in the body gives positive_value(1).
positive_value(Var) :-
    positive_body_literal(Slot, _, Pred, _),
    positive_arg(Pred, Arg),
    var_at(body, Slot, Arg, Var).

% DEFINITION, reusable. positive_value(Result), case 2: a sum of two positive
% values is positive.
%   Slot         body slot of "Left + Right = Result" (unused beyond the join).
%   Left, Right  operand variable ids, both already positive.
%   Result       variable id of the sum, derived positive.
positive_value(Result) :-
    addition(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right).

% DEFINITION, reusable. positive_value(Value), case 3: if Value + Value is
% positive, Value is positive.
%   Slot    body slot of "Value + Value = Result".
%   Value   the variable id used as both operands, derived positive.
%   Result  variable id of the sum, already positive.
positive_value(Value) :-
    addition(Slot, Value, Value, Result),
    positive_value(Result).

% DEFINITION, reusable. positive_value(Result), case 4: a product of two
% positive values is positive.
%   Slot         body slot of "Left * Right = Result".
%   Left, Right  operand variable ids, both already positive.
%   Result       variable id of the product, derived positive.
positive_value(Result) :-
    multiplication(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right).

% DEFINITION, reusable. positive_value(Greater), case 5: a value above a
% positive value is positive.
%   Smaller  variable id already positive.
%   Greater  variable id with an explicit "Smaller < Greater" in the body.
positive_value(Greater) :- selected_lt(Smaller, Greater), positive_value(Smaller).

% DEFINITION, reusable. positive_value(Greater), case 6: the same through an
% explicit "Smaller <= Greater".
positive_value(Greater) :- selected_leq(Smaller, Greater), positive_value(Smaller).

% ----- representation/arithmetic.lp -----

% DEFINITION, reusable. addition(Slot, Left, Right, Result): the body states
% Left + Right = Result.
%   Slot    body slot of the literal.
%   Left    variable id of the left operand.
%   Right   variable id of the right operand.
%   Result  variable id of the sum.
% Example: "V0+V1=V2" in slot 3 yields addition(3,0,1,2). Shared by
% inference/numeric.lp (sign and order consequences),
% pruning/contradictions/numeric.lp and pruning/redundancy/numeric.lp.
addition(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), add_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).

% DEFINITION, reusable. multiplication(Slot, Left, Right, Result): the body
% states Left * Right = Result.
%   Arguments as in addition/4, Result being the product.
% Shared by inference/numeric.lp and pruning/contradictions/numeric.lp.
multiplication(Slot, Left, Right, Result) :-
    selected(body, Slot, Mode), mul_mode(Mode),
    arithmetic_operand(Slot, left, Left), arithmetic_operand(Slot, right, Right),
    arithmetic_result(Slot, Result).

% Views of recognized three-placeholder arithmetic templates. Specialized
% mode flags preserve the compiler eligibility checks; these are not a new
% operator alphabet. Variable arguments are ids, not numeric values.

% DEFINITION, reusable. arithmetic_operand(Slot, Side, Variable): an operand
% of the arithmetic literal at body Slot.
%   Slot      body slot holding a complete template "Left op Right = Result".
%   Side      left or right, as declared in the template.
%   Variable  variable id written at that operand.
% Translates the storage position into a role, so no consumer computes
% offsets. Shared by the operator views below, legality/asp_safety.lp,
% legality/flow/closure.lp, symmetry/arithmetic.lp and
% pruning/redundancy/arithmetic.lp.
arithmetic_operand(Slot, Side, Variable) :-
    selected(body, Slot, Mode), mode_arithmetic_operand(Mode, Side, Position),
    var_at(body, Slot, Position, Variable).

% DEFINITION, reusable. arithmetic_result(Slot, Variable): the result of the
% arithmetic literal at body Slot.
%   Slot      body slot holding a complete arithmetic template.
%   Variable  variable id written at the result placeholder.
% Shared by the operator views below, legality/asp_safety.lp,
% legality/flow/closure.lp and pruning/redundancy/arithmetic.lp.
arithmetic_result(Slot, Variable) :-
    selected(body, Slot, Mode), mode_arithmetic_result(Mode, Position),
    var_at(body, Slot, Position, Variable).

% ----- representation/operators.lp -----

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

% ----- pruning/redundancy/tautologies.lp -----

% Lin and Chen, "Discovering Classes of Strongly Equivalent Logic Programs",
% IJCAI 2005, Theorem 5 (the 0-1-0 problem): a rule is strongly equivalent to
% the empty program if a positive body atom also occurs in its head or its
% default-negated body. https://cse.hkust.edu.hk/faculty/flin/papers/selp-disc-ijcai05.pdf
%
% Compare complete signed atoms: same predicate, recursive term shape and
% variable bindings. Positive/negative body overlap makes the body impossible.
% Positive body/head overlap is a tautology for normal or disjunctive heads;
% choice and cardinality heads need a separate argument and are not pruned here.

% CONSTRAINT. The body may not contain an atom together with its default
% negation: such a body is never satisfied, so the clause does nothing.
%   PosSlot          body slot of the positive atom.
%   NegSlot, NegMode body slot and mode of the negated atom, which must be a
%                    single "not"; "not not p" is excluded from this check.
%   Pred, Arity      the predicate both share.
%   pruned: h(V0) :- p(V0,V1), not p(V0,V1).
%   kept:   h(V0) :- p(V0,V1), not p(V1,V0).       different atoms
%   kept:   h(V0) :- p(V0), not not p(V0).         double negation
:- positive_body_literal(PosSlot, _, Pred, Arity),
    negative_body_literal(NegSlot, NegMode, Pred, Arity),
    not double_negative_mode(NegMode),
    same_term_bindings(body, PosSlot, body, NegSlot).

% ----- representation/literals.lp -----

% DEFINITION, reusable. negative_body_literal(Slot, Mode, Pred, Arity): the
% body holds "not Pred(...)" or "not not Pred(...)" at Slot.
%   Arguments as in positive_body_literal/4.
% Shared by legality/asp_safety.lp (negated variables need support),
% pruning/redundancy/literals.lp and tautologies.lp, and the property files
% that detect a negation made redundant or impossible by a property.
negative_body_literal(Slot, Mode, Pred, Arity) :-
    negative_normal_literal(body, Slot, Mode, Pred, Arity).

% DEFINITION, local helper. negative_normal_literal(Section, Slot, Mode, Pred,
% Arity): a selected plain atom under "not" or "not not".
%   Arguments as in normal_literal/5.
% Used only by negative_body_literal below.
negative_normal_literal(Section, Slot, Mode, Pred, Arity) :-
    normal_literal(Section, Slot, Mode, Pred, Arity),
    negative_mode(Mode).

% ----- pruning/redundancy/tautologies.lp -----

% CONSTRAINT. A plain or disjunctive head may not repeat a positive body
% atom: the clause would only derive what its body already requires.
%   HeadSlot, HeadMode  the head literal; an unconditional atom of a normal or
%                       disjunctive head (plain_disjunctive_head_mode).
%   BodySlot            body slot of the identical positive atom.
%   Pred, Arity         the predicate both share.
%   pruned: p(V0) :- p(V0), q(V0).
%   pruned: p(V0);r(V0) :- p(V0).
%   kept:   p(V0) :- p(V1), q(V0,V1).              different atoms: recursion
%   kept:   {p(V0)} :- p(V0).                      choice heads are not pruned
:- selected(head, HeadSlot, HeadMode),
    plain_disjunctive_head_mode(HeadMode),
    head_literal(HeadSlot, HeadMode, Pred, Arity),
    positive_body_literal(BodySlot, _, Pred, Arity),
    same_term_bindings(head, HeadSlot, body, BodySlot).

% ----- representation/literals.lp -----

% DEFINITION, reusable. positive_body_literal(Slot, Mode, Pred, Arity): the
% body holds the positive plain atom Pred at Slot.
%   Slot   body slot.
%   Mode   id of the selected template.
%   Pred   signed predicate id.
%   Arity  source arity of Pred.
% The most shared view of the program: only such a literal grounds its
% variables and asserts that a tuple of Pred is true, so inference/numeric.lp,
% legality/asp_safety.lp, pruning/redundancy/tautologies.lp and almost every
% pruning/properties file start from it.
positive_body_literal(Slot, Mode, Pred, Arity) :-
    positive_normal_literal(body, Slot, Mode, Pred, Arity).

% DEFINITION, reusable. head_literal(Slot, Mode, Pred, Arity): the clause can
% derive an atom of Pred through head Slot.
%   Slot   head slot.
%   Mode   id of the selected head template.
%   Pred   signed predicate id the head defines.
%   Arity  source arity of Pred.
% Shared by legality/invention.lp (what the clause defines),
% pruning/redundancy/tautologies.lp and pruning/properties/implies.lp and
% project_implies.lp (a head the body already guarantees).
% Case 1: a plain positive head atom, as in "p(V0) :- ..." or "p(V0);q(V0)".
head_literal(Slot, Mode, Pred, Arity) :-
    positive_normal_literal(head, Slot, Mode, Pred, Arity).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: the conclusion of a conditional head element, as in
% "p(V0) : q(V0)".
head_literal(Slot, Mode, Pred, Arity) :-
    conditional_head_literal(Slot, Mode, Pred, Arity).

% DEFINITION, reusable. Same predicate and arguments.
% Case 3: the atom of a choice, cardinality or aggregate head element that is
% not default negated, as in "{p(V0) : q(V0)}".
head_literal(Slot, Mode, Pred, Arity) :-
    selected(head, Slot, Mode), head_aggregate_mode(Mode),
    mode_atom(Mode, Pred, Arity), not negative_mode(Mode).

% DEFINITION, reusable. positive_normal_literal(Section, Slot, Mode, Pred,
% Arity): a selected plain atom without default negation.
%   Arguments as in normal_literal/5.
% Shared by positive_body_literal and head_literal below and by
% pruning/redundancy/literals.lp, which compares positive atoms in both
% sections.
positive_normal_literal(Section, Slot, Mode, Pred, Arity) :-
    normal_literal(Section, Slot, Mode, Pred, Arity),
    positive_mode(Mode).

% Classify selected literals for safety and pruning consumers.
% Normal literals exclude comparisons, arithmetic, aggregates and conditionals.
% Head classification also includes conclusions of conditional head elements.

% DEFINITION, reusable. positive_mode(Mode): Mode is not under default negation.
%   Mode  id of any compiled template that has a mode_kind and no
%         negative_mode fact. "not not p" is a negative_mode, so it is excluded.
% Shared by positive_normal_literal below and by legality/flow/seeds.lp, which
% lets only positive normal atoms bind variables.
positive_mode(Mode) :-
    mode_kind(Mode, _),
    not negative_mode(Mode).

% DEFINITION, reusable. normal_literal(Section, Slot, Mode, Pred, Arity): a
% plain atom of either polarity is selected.
%   Section  head or body.
%   Slot     slot position inside the section.
%   Mode     id of the selected normal template.
%   Pred     signed predicate id of its atom; p/n and -p/n are different ids.
%   Arity    arity of that predicate as written in the source.
% Joins selected/3 with the atom signature once. Shared by the polarity views
% below and by legality/invention.lp, pruning/redundancy/literals.lp and
% several pruning/properties files that treat both polarities alike.
normal_literal(Section, Slot, Mode, Pred, Arity) :-
    selected(Section, Slot, Mode),
    normal_mode(Mode),
    mode_atom(Mode, Pred, Arity).

% ----- representation/conditionals.lp -----

% DEFINITION, reusable. conditional_head_literal(Slot, Mode, Pred, Arity): a
% conditional head element concludes an atom of Pred.
%   Slot   head slot.
%   Mode   id of the selected conditional template.
%   Pred   signed predicate id of the conclusion.
%   Arity  source arity of the conclusion, not the width of the whole template.
% A default-negated conclusion ("not p(V0) : q(V0)") defines nothing and is
% excluded. Consumed by representation/literals.lp as one case of head_literal.
conditional_head_literal(Slot, Mode, Pred, Arity) :-
    selected(head, Slot, Mode),
    conditional_mode(Mode), mode_atom(Mode, Pred, Arity),
    not negative_mode(Mode).

% ----- representation/literals.lp -----

% DEFINITION, reusable. conditional_mode(Mode): Mode is a conditional literal
% "conclusion : conditions".
%   Mode  id of a template of kind conditional.
% Shared by representation/conditionals.lp, legality/scopes.lp and
% legality/flow/declarations.lp, seeds.lp and requirements.lp, which all treat
% conditionals apart because their variables can be local.
conditional_mode(Mode) :- mode_kind(Mode, conditional).
% DEFINITION, local helper. head_aggregate_mode(Mode): Mode is one element of
% a choice, cardinality or function aggregate head.
%   Mode  id of a template of kind head_aggregate.
% Used only by the third head_literal rule below.
head_aggregate_mode(Mode) :- mode_kind(Mode, head_aggregate).

% ----- representation/tuples.lp -----

% DEFINITION, reusable. same_term_bindings(Section0, Slot0, Section1, Slot1):
% two different selected literals have the same arguments.
%   Section0, Slot0  first selected literal.
%   Section1, Slot1  second selected literal.
% "Same arguments" means equal mode_shape (same nesting, functors and
% constants) and equal variable ids at every placeholder. Predicate and
% polarity are NOT compared: p(V0,V1) and "not q(V0,V1)" satisfy it, and each
% consumer adds the predicate relation it needs. Shared by
% pruning/redundancy/literals.lp and tautologies.lp and by
% pruning/properties/implies.lp, mutex.lp, equivalent.lp, complement.lp,
% partition.lp and subsumption.lp.
% Case 1: the literals are in different sections (one head, one body).
same_term_bindings(Section0, Slot0, Section1, Slot1) :-
    selected_shape(Section0, Slot0, Shape),
    selected_shape(Section1, Slot1, Shape),
    Section0 != Section1,
    not different_variable_binding(Section0, Slot0, Section1, Slot1).

% DEFINITION, reusable. Same arguments; predicate and polarity are not compared.
% Case 2: both literals are in the same section, at different slots. It holds
% in both slot orders.
same_term_bindings(Section, Slot0, Section, Slot1) :-
    selected_shape(Section, Slot0, Shape),
    selected_shape(Section, Slot1, Shape),
    Slot0 != Slot1,
    not different_variable_binding(Section, Slot0, Section, Slot1).

% DEFINITION, local helper. different_variable_binding(Section0, Slot0,
% Section1, Slot1): two selected literals of equal term shape disagree at
% some placeholder.
%   Section0, Slot0  first selected literal.
%   Section1, Slot1  a different selected literal whose mode has the same
%                    mode_shape, hence the same placeholder positions.
% Holds when some placeholder carries different variable ids, as position 1
% of p(V0,V1) and p(V0,V2). Every placeholder holds exactly one variable, so
% "the second literal does not hold Var there" says the two ids differ
% without grounding every pair of ids. Used only, negated, by
% same_term_bindings below, which asks about exactly these pairs.
% Every true var_at belongs to a placeholder of the unique selected mode,
% by representation/arguments.lp, so it already implies mode_variable_arg.
different_variable_binding(Section0, Slot0, Section1, Slot1) :-
    selected_shape(Section0, Slot0, Shape),
    selected_shape(Section1, Slot1, Shape),
    (Section0, Slot0) != (Section1, Slot1),
    var_at(Section0, Slot0, Arg, Var),
    not var_at(Section1, Slot1, Arg, Var).

% Structural relations shared by duplicate, property and safety checks.
% same_term_bindings requires the same recursive term shape as well as variable ids;
% matching variables alone would conflate different constants or functors.
% Pair relations exclude a slot compared with itself.

% DEFINITION, local helper. selected_shape(Section, Slot, Shape): recursive
% argument shape of the unique mode selected at this slot.
%   Section, Slot  an occupied head or body slot.
%   Shape          mode_shape of its selected mode, excluding predicate/sign.
% Project once before comparing slots: many modes share the same shape, so
% joining selected modes in every comparison would ground their Cartesian
% product. Used only by the binding comparisons below.
selected_shape(Section, Slot, Shape) :-
    selected(Section, Slot, Mode), mode_shape(Mode, Shape).

% ----- pruning/redundancy/theta.lp -----

% CONSTRAINT (enumerated-offset encoding). Reject a clause that a substitution
% folds onto a proper subclause of itself: it is equivalent to that shorter
% clause, which is enumerated on its own.
%   pruned: q(X) :- p(X,Y), p(X,Z).       Z -> Y drops p(X,Z); q(X) :- p(X,Y)
%                                         says the same
%   kept:   q(X) :- p(X,Y), p(Y,Z).       no substitution drops an atom
%   kept:   q(Y) :- p(X,Y), p(X,Z), Y != Z.   Z is fixed by the comparison
:- theta_witness.

% DEFINITION, local helper. theta_witness: some offset combination is a valid
% substitution that leaves a repeated literal without preimage. It has no
% arguments: one witness is enough to condemn the clause.
%   Omitted  (body variable) slot of the repeated literal that gets dropped.
%   Id       (body variable) the combination that proves it.
theta_witness :-
    theta_sigma_section(Section), theta_repeated(Section, Omitted),
    theta_sigma(Id), not theta_bad(Id), not theta_uses(Id, Section, Omitted).

% DEFINITION, local helper. theta_bad(Id): offset combination Id is not a
% substitution of the current clause.
%   Id  id of one combination enumerated by Python; theta_sigma_offset(Id,
%       Section, Slot, Offset) gives the offset it assigns to each body slot.
% Case 1: it assigns a blocked move to some repeated literal.
theta_bad(Id) :-
    theta_sigma_offset(Id, Section, Slot, Offset), theta_blocked(Section, Slot, Offset).
% DEFINITION, local helper. Same predicate. Case 2: two of its moves clash.
theta_bad(Id) :-
    theta_sigma_offset(Id, Section, Slot, Offset),
    theta_sigma_offset(Id, Section, Other, OtherOffset), Slot <= Other,
    theta_clash(Section, Slot, Offset, Other, OtherOffset).

% A move is blocked when Offset leaves the group or moves a fixed variable.
% DEFINITION, local helper. theta_blocked(Section, Slot, Offset): that move is
% not allowed on its own.
%   Section, Slot  a repeated literal.
%   Offset         an enumerated offset.
% Case 1: Start + Offset is not a slot of the same mode.
theta_blocked(Section, Slot, Offset) :-
    theta_group_start(Section, Slot, _), theta_offset(Section, Offset),
    not theta_move(Section, Slot, Offset, _).
% DEFINITION, local helper. Same predicate. Case 2: the move would send a
% fixed variable to a different variable.
%   Position  placeholder of Slot that holds the fixed variable Var.
theta_blocked(Section, Slot, Offset) :-
    theta_move(Section, Slot, Offset, _),
    var_at(Section, Slot, Position, Var), theta_fixed(Var),
    not theta_image(Section, Slot, Offset, Position, Var).

% Two moves clash when they send one variable to different images.
% DEFINITION, local helper. theta_clash(Section, Slot, Offset, Other,
% OtherOffset): the two moves cannot belong to one substitution.
%   Section         the theta section.
%   Slot, Offset    a move of one repeated literal.
%   Other, OtherOffset
%                   a move of a literal sharing a variable with it (possibly
%                   the same literal, at another position). The shared
%                   variable gets one image from the first move and a
%                   different one, or none, from the second.
theta_clash(Section, Slot, Offset, Other, OtherOffset) :-
    theta_shared(Section, Slot, Position, Other, OtherPosition),
    theta_image(Section, Slot, Offset, Position, Image),
    theta_offset(Section, OtherOffset),
    not theta_image(Section, Other, OtherOffset, OtherPosition, Image).

% theta_image(Section, Slot, Offset, Position, Image): after that move, the
% variable at Position of Slot becomes Image.
% DEFINITION, local helper.
%   Section, Slot, Offset  the move.
%   Position               a placeholder position of the literal.
%   Image                  variable id the target literal holds at the same
%                          position. Moving p(X,Z) onto p(X,Y) gives image X
%                          at position 0 and image Y at position 1.
theta_image(Section, Slot, Offset, Position, Image) :-
    theta_move(Section, Slot, Offset, Target),
    var_at(Section, Target, Position, Image).

% theta_shared(Section, Slot, Position, Other, OtherPosition): two positions of
% repeated literals hold the same variable, ordered to list each pair once.
% DEFINITION, local helper.
%   Section         the theta section.
%   Slot, Position  a placeholder of a repeated literal.
%   Other, OtherPosition
%                   a later placeholder, of the same or of another repeated
%                   literal, that holds the same variable.
theta_shared(Section, Slot, Position, Other, OtherPosition) :-
    theta_repeated(Section, Slot), theta_repeated(Section, Other),
    var_at(Section, Slot, Position, Var), var_at(Section, Other, OtherPosition, Var),
    (Slot, Position) < (Other, OtherPosition).

% DEFINITION, local helper. theta_uses(Id, Section, Target): combination Id
% maps some repeated literal onto Target.
%   Id       id of the offset combination.
%   Section  the theta section.
%   Target   a slot that is the image of at least one literal; a slot that
%            no literal maps to is dropped by the substitution.
theta_uses(Id, Section, Target) :-
    theta_sigma_offset(Id, Section, Slot, Offset), theta_move(Section, Slot, Offset, Target).

% theta_move(Section, Slot, Offset, Target): Offset sends Slot onto Target.
% DEFINITION, local helper.
%   Section  the theta section.
%   Slot     slot of a repeated literal, the source of the move.
%   Offset   the offset applied to it.
%   Target   Start + Offset, accepted only when it holds the same mode as
%            Slot (it stays inside the group). Target = Slot is the identity
%            move.
theta_move(Section, Slot, Offset, Target) :-
    theta_group_start(Section, Slot, Start), theta_offset(Section, Offset),
    Target = Start + Offset,
    selected(Section, Slot, Mode), selected(Section, Target, Mode).

% Enumerated offsets (a normal program). Equal modes occupy contiguous slots
% (symmetry/slots.lp), so a repeated literal maps to Start + Offset, where Start
% is the first slot of its mode. theta_sigma(Id) with theta_sigma_offset(Id,
% Section, Slot, Offset) lists every offset combination; they depend on no
% model, so "some combination is a consistent substitution avoiding O" is
% stratified negation and no disjunction is needed.
%
% Consistency is checked per move and per pair of moves, never per Id and
% variable: a combination is a substitution iff each move keeps fixed variables
% and every two moves agree on the image of each shared variable. Only these
% slot-level verdicts are joined with the offset combinations, so the ground
% size no longer multiplies the combinations by variables and images.

% DEFINITION, local helper. theta_group_start(Section, Slot, Start): where the
% run of literals sharing the mode of Slot begins.
%   Section  the theta section, under the enumerated-offset encoding.
%   Slot     slot of a repeated literal.
%   Start    the smallest slot holding the same mode. In "p, p, p, o, o" at
%            slots 0..4, every p has Start 0 and every o has Start 3.
theta_group_start(Section, Slot, Start) :-
    theta_sigma_section(Section), theta_repeated(Section, Slot),
    selected(Section, Slot, Mode),
    Start = #min { Other : selected(Section, Other, Mode) }.

% DEFINITION, local helper. theta_offset(Section, Offset): an offset value
% that Python enumerated.
%   Section  the theta section.
%   Offset   integer from 0 up to the largest mode group the body can hold,
%            minus one.
theta_offset(Section, Offset) :- theta_sigma_offset(_, Section, _, Offset).

% CONSTRAINT (saturation encoding). Every omission must end saturated. If a
% substitution dropping (OS, O) exists, the saturated interpretation is not
% minimal, and the only other candidate models have theta_unfolded(OS, O)
% false and are rejected here: the clause has no model. It prunes and keeps
% exactly the clauses of the enumerated-offset constraint above.
%   pruned: q(X) :- p(X,Y), p(X,Z).
%   kept:   q(X) :- p(X,Y), p(Y,Z).
:- theta_omission(OS, O), not theta_unfolded(OS, O).

% CHOICE (disjunctive guess). For each omission and each pair of variables,
% either the substitution maps Var to Image or it does not.
%   OS, O  the omitted literal (section, slot).
%   Var    source variable id.
%   Image  candidate image variable id.
%   theta_map      the guess "Var is sent to Image".
%   theta_not_map  its explicit complement, needed because saturation cannot
%                  use default negation on the guessed atoms.
theta_map(OS, O, Var, Image) | theta_not_map(OS, O, Var, Image) :-
    theta_omission(OS, O), theta_variable(Var), theta_variable(Image).
% DEFINITION, local helper (disjunctive). Every variable has at least one
% image: the head is the disjunction of theta_map(OS, O, Var, Image) over all
% candidate images.
theta_map(OS, O, Var, Image) : theta_variable(Image) :-
    theta_omission(OS, O), theta_variable(Var).

% DEFINITION, local helper (saturation). Once a guess has failed, make every
% theta_map atom of that omission true.
%   OS, O       the omission whose guess failed.
%   Var, Image  every pair of variables.
% All failed guesses thereby collapse into one maximal interpretation, which
% is stable only if no smaller, successful guess exists.
theta_map(OS, O, Var, Image) :-
    theta_unfolded(OS, O), theta_variable(Var), theta_variable(Image).
% DEFINITION, local helper (saturation). The same for every theta_not_map
% atom of that omission.
theta_not_map(OS, O, Var, Image) :-
    theta_unfolded(OS, O), theta_variable(Var), theta_variable(Image).

% DEFINITION, local helper. theta_unfolded(OS, O): the current guess fails to
% be a substitution that drops literal (OS, O).
%   OS, O  the omitted literal (section, slot).
% Case 1: the guess is incoherent, Var both mapped and not mapped to Image.
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_map(OS, O, Var, Image), theta_not_map(OS, O, Var, Image).
% DEFINITION, local helper. Same predicate. Case 2: the guess is not a
% function, Var has two different images.
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_map(OS, O, Var, Image), theta_map(OS, O, Var, Other),
    Image != Other.
% DEFINITION, local helper. Same predicate. Case 3: the guess moves a fixed
% variable.
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_map(OS, O, Var, Image), theta_fixed(Var), Image != Var.

% DEFINITION, local helper. theta_candidate(OS, O, Section, Source, Target):
% a literal that Source may be mapped onto while (OS, O) is omitted.
%   OS, O    the omitted literal.
%   Section  section of the source literal.
%   Source   slot of a repeated literal.
%   Target   a slot of the same mode, other than the omitted one. It may be
%            Source itself.
theta_candidate(OS, O, Section, Source, Target) :-
    theta_omission(OS, O), theta_repeated(Section, Source),
    selected(Section, Source, Mode), selected(Section, Target, Mode),
    (Section, Target) != (OS, O).
% DEFINITION, local helper. theta_mismatch(OS, O, Section, Source, Target):
% the guess does not send Source onto that candidate Target.
%   Arguments as in theta_candidate/5.
% It holds when, at some placeholder position, the guess does not map the
% variable of Source to the variable of Target.
theta_mismatch(OS, O, Section, Source, Target) :-
    theta_candidate(OS, O, Section, Source, Target),
    var_at(Section, Source, Position, Var),
    var_at(Section, Target, Position, Image),
    theta_not_map(OS, O, Var, Image).
% DEFINITION, local helper. theta_unfolded, case 4: some repeated literal
% Source has no image at all: the guess mismatches every one of its
% candidates (the conditional literal in the body ranges over all of them).
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_repeated(Section, Source),
    theta_mismatch(OS, O, Section, Source, Target) :
        theta_candidate(OS, O, Section, Source, Target).

% Saturation fallback for many offset combinations. theta_map guesses the image
% of every variable; theta_unfolded saturates when the guess is not a
% substitution folding the clause without Omitted. The saturated interpretation
% is stable exactly when no substitution exists: a witness defeats minimality.
% This makes the program disjunctive, so Python uses it only when enumerating
% offsets would ground too much.
%
% In the rules below (OS, O) names the literal being omitted: OS is its
% section and O its slot.

% DEFINITION, local helper. theta_omission(Section, Omitted): one subproblem
% of the saturation check, "is there a substitution that drops this literal?".
%   Section  the theta section, under the saturation encoding.
%   Omitted  slot of a repeated literal.
theta_omission(Section, Omitted) :-
    theta_saturated_section(Section), theta_repeated(Section, Omitted).

% DEFINITION, local helper. theta_variable(Var): Var takes part in the
% guessed substitution.
%   Var  any variable id used in the clause, as soon as the check is active
%        under the saturation encoding. It serves as both source and image.
theta_variable(Var) :-
    theta_saturated_section(_), theta_active, var_at(_, _, _, Var).

% DEFINITION, local helper. theta_fixed(Var): any substitution must map Var
% to itself.
%   Var  variable id that occurs in a literal that does not move: the head, a
%        comparison, arithmetic, an aggregate, a conditional, or an atom whose
%        mode is selected only once.
theta_fixed(Var) :-
    theta_active, var_at(Section, Slot, _, Var), not theta_repeated(Section, Slot).

% Only a clause repeating a movable mode can be theta-redundant.
% DEFINITION, local helper. theta_repeated(Section, Slot): the literal at that
% slot is a candidate to move or to be dropped.
%   Section  the theta section (body).
%   Slot     slot of a movable literal whose mode is also selected at another
%            slot. In "p(X,Y), p(X,Z), o(Y)" with both modes repeatable, the
%            two p literals are repeated and o(Y) is not.
theta_repeated(Section, Slot) :-
    theta_section(Section),
    selected(Section, Slot, Mode), theta_movable(Mode, Section),
    selected(Section, Other, Mode), Slot != Other.
% DEFINITION, local helper. theta_active: the current clause repeats at least
% one movable literal. It has no arguments; it switches on the rest of the
% check for this model.
theta_active :- theta_repeated(_, _).

% Theta reduction: reject a clause C when a substitution theta maps every
% literal of C onto a literal of C other than some selected literal O. Then
% C is equivalent to its proper subclause C theta, which is also enumerated.
%
% Movable literals are normal body atoms (either polarity) of a mode with
% recall > 1. Every other literal, and every literal whose mode occurs once,
% maps to itself and fixes its variables: comparisons, arithmetic, aggregates,
% conditionals and every head stay untouched instead of blocking the check.
% Head literals never move because dropping one can leave the language:
%   kept:   p(X);p(Y) :- d(X), d(Y).   Y -> X gives p(X) :- d(X), equivalent but
%                                     not generated under #minhl(2)
%
%   pruned: q(X) :- p(X,Y), p(X,Z).            Z -> Y maps p(X,Z) onto p(X,Y)
%   pruned: :- r(A,B), r(A,C), s(A,D), B != D.  C -> B; B and D stay fixed
%   pruned: q(X) :- p(X,Y), p(X,Z), o(Y), o(Z). Z -> Y folds p and o together
%   kept:   q(X) :- p(X,Y), p(Y,Z).            no substitution folds either atom
%   kept:   :- r(A,B), r(A,C), B != C.          C occurs in the comparison
%
% Python chooses one of two exact encodings of "some substitution exists":
% enumerated offsets while they stay few, saturation otherwise.
%
% Every predicate of this file is a local helper: no other module uses it.

% DEFINITION, local helper. theta_movable(Mode, body): literals of Mode may be
% mapped onto one another by a substitution.
%   Mode  id of a plain atom template of the body, of either polarity, whose
%         recall allows more than one occurrence.
%   body  the section; only body atoms move.
% With recall 1 no clause repeats the mode, so nothing about it is grounded.
theta_movable(Mode, body) :-
    mode_section(Mode, body), normal_mode(Mode), mode_recall(Mode, Recall), Recall > 1.

% ----- representation/literals.lp -----

% DEFINITION, reusable. normal_mode(Mode): Mode is a plain (possibly negated)
% atom.
%   Mode  id of a template of kind normal: not a comparison, arithmetic,
%         aggregate, conditional or boolean literal.
% Shared by normal_literal below, legality/flow/seeds.lp (binding modes) and
% pruning/redundancy/literals.lp and theta.lp (which literals may repeat/move).
normal_mode(Mode) :- mode_kind(Mode, normal).

% ----- pruning/redundancy/theta.lp -----

% DEFINITION, local helper. theta_section(Section): theta reduction is active
% for that section, under either encoding.
%   Section  body, when Python emitted theta_sigma_section(body) (enumerated
%            offsets) or theta_saturated_section(body) (saturation). With
%            neither fact the whole file is inert.
% Case 1: the enumerated-offset encoding.
theta_section(Section) :- theta_sigma_section(Section).
% DEFINITION, local helper. Same predicate. Case 2: the saturation encoding.
theta_section(Section) :- theta_saturated_section(Section).

% ----- pruning/task/optional_constraints.lp -----

% Task-relative pruning, not ASP equivalence. Python proves a learned head is
% necessary for a perfect hypothesis before emitting prune_optional_constraints.

% CONSTRAINT. When Python emits prune_optional_constraints, no headless
% clause is generated.
%   prune_optional_constraints  flag fact: static analysis of this
%                               positive-only task proved that a perfect
%                               hypothesis needs a learned headed clause.
% With the flag:
%   pruned: :- edge(V0,V1).
%   kept:   target(V0) :- edge(V0,V1).
% Without the flag this constraint is inert and both clauses are kept.
:- prune_optional_constraints, not selected_slot(head, _).

% ==========================================================================
% 4. Input vocabulary: facts emitted by Python and cross-module views
% ==========================================================================

% Generation limits and feature switches.

% max_vars(Max): the candidate may use variable ids 0 through Max-1.
#defined max_vars/1.

% max_body(Max): the body exposes slots 0 through Max-1.
#defined max_body/1.

% enumerate_by_size: incremental generation requests models grouped by the
% total number of selected body literals and attached conditions.
#defined enumerate_by_size/0.

% Optional exact domains: complete flat mode, alias placeholder and its earlier
% root. Argument equality/distinctness still keeps its original constraints.
#defined binding_flat_mode/1.
#defined binding_alias/3.

% prune_optional_constraints: static task analysis proved that a perfect
% hypothesis for this positive-only task needs a learned headed clause.
#defined prune_optional_constraints/0.

% positive_arg(Pred, Arg) / nonnegative_arg(Pred, Arg): every value closed
% predicate Pred takes at source argument Arg, in every model of every context,
% is an integer > 0 or >= 0. They are evidence for sound numeric consequences of
% variables a positive body literal grounds there.
#defined positive_arg/2.
#defined nonnegative_arg/2.

% Core mode identity and shape.

% mode_section(Mode, Section): where this template may occur.
#defined mode_section/2.

% mode_kind(Mode, Kind): syntactic family, one of normal, conditional,
% comparison, arithmetic, aggregate, head_aggregate or boolean.
#defined mode_kind/2.

% plain_disjunctive_head_mode(Mode): Mode is an unconditional atom in a normal
% or disjunctive head. Negated disjuncts, choice/cardinality and conditioned
% heads are absent.
#defined plain_disjunctive_head_mode/1.

% mode_recall(Mode, Recall): effective maximum occurrences of this mode after
% replacing an unlimited source recall with the finite structural bound.
#defined mode_recall/2.

% recall_group(Mode, Group): modes expanded from the same declaration share a
% recall budget identified by Group.
#defined recall_group/2.

% mode_shape(Mode, Shape): id of the complete recursive term shape used when
% testing whether two selected occurrences have identical term structure.
#defined mode_shape/2.

% mode_atom(Mode, Predicate, Arity): predicate signature represented by a
% normal mode, the conclusion of a conditional mode, or an element of a head
% aggregate. Operators and body aggregates intentionally have no mode_atom fact.
#defined mode_atom/3.

% negative_mode(Mode): the atom, conditional conclusion, or head aggregate
% element is under default negation and cannot produce globally bound variables.
#defined negative_mode/1.

% double_negative_mode(Mode): the negated form is `not not`; it is also a
% negative_mode.
#defined double_negative_mode/1.

% conditional_mode(Mode): cross-module view derived from
% mode_kind(Mode, conditional).
#defined conditional_mode/1.

% Argument schema. Position follows the convention above: a source argument
% index for plain atoms, a flattened binding otherwise. A fixed term occupies no
% Position and a structured term can occupy several.

% mode_variable_arg(Mode, Position): Position is a variable placeholder of Mode.
#defined mode_variable_arg/2.

% first_occurrence_bound(Section, Slot, Position, Bound): number of possible
% earlier variable-placeholder positions in body-before-head tuple order.
% Derived by symmetry/variables.lp; representation/arguments.lp draws only
% ids <= Bound from the unchanged var/1 domain. It overapproximates actual
% earlier occurrences across all declared modes and head forms.
#defined first_occurrence_bound/4.

% mode_arg_type(Mode, Position, Type): nominal type required at Position.
% Positions declared as any deliberately have no fact.
#defined mode_arg_type/3.

% mode_arg_direction(Mode, Position, Direction): input, output or any.
% Every variable placeholder with a declared direction has one fact.
#defined mode_arg_direction/3.

% Binding alternatives of a positive body atom whose placeholders do not all
% ground their variable: a pool expands into alternatives, and a placeholder
% inside non-invertible arithmetic (q(X+Y), q(|X|), q(X/2)) grounds nothing.
% A variable is grounding-safe through that atom only if every alternative
% lists a position holding it. Positions refer to flattened placeholders.
#defined mode_pool_alternative/2.
#defined mode_pool_alternative_arg/3.

% A positive condition binds a local variable only if every binding
% alternative contains it (pools and non-invertible arithmetic). Scope and Element identify its local region.
#defined local_pool_condition_arg/5.
#defined local_pool_alternative/5.
#defined local_pool_alternative_arg/6.

% mode_arg_label(Mode, Position, Label): source label attached to this mode
% position, used to preserve declared argument identity.
#defined mode_arg_label/3.

% relation_output_mode(Mode): a comparison template has at least one output
% binding and is therefore treated as a relation that can produce a value.
#defined relation_output_mode/1.

% Compound heads and labels.

% head_form_member(Form, Slot, Mode): Form contains Mode at head Slot. Selecting
% a form selects all of its members; the members are not independent choices.
#defined head_form_member/3.

% composite_head_form(Form): Form is a choice, cardinality or function aggregate
% head. Its elements form one linked component.
#defined composite_head_form/1.

% head_arg_label(Form, Mode, Position, Label): labelled position inside one
% compound head form; labels with the same name must denote one variable.
#defined head_arg_label/4.

% Conditional-literal schema.

% conditional_main_arg(Mode, Position): Position belongs to the conclusion of
% the conditional literal rather than to an attached condition.
#defined conditional_main_arg/2.

% conditional_condition(Mode, Condition, Predicate, Polarity): Condition is an
% atom occurrence with its signed predicate id and positive/negative polarity.
% Comparison conditions have no predicate signature and omit this fact.
#defined conditional_condition/4.

% conditional_condition_arg(Mode, Condition, Argument, Position): source
% Argument of one condition occurrence maps to flattened Position in Mode.
#defined conditional_condition_arg/4.

% conditional_condition_variant(Mode, Condition, Variant): canonical id of the
% complete condition syntax, including the type, direction and label of each
% placeholder, used only to order or deduplicate equal variants. Conditions
% that differ in any of those cannot swap places.
#defined conditional_condition_variant/3.

% conditional_shorter_mode(Mode, Condition): the language also contains Mode's
% template without condition Condition, so a repeated condition is removable.
#defined conditional_shorter_mode/2.

% Theta reduction (pruning/redundancy/theta.lp). A section holding repeatable
% movable literals gets exactly one of two encodings. theta_sigma_section with
% theta_sigma(Id) and theta_sigma_offset(Id, Section, Slot, Offset) enumerate
% every offset combination: the literal in Slot maps to the first slot of its
% mode group plus Offset. theta_saturated_section selects the disjunctive
% saturation instead, used only when those combinations would be too many.
#defined theta_sigma_section/1.
#defined theta_sigma/1.
#defined theta_sigma_offset/4.
#defined theta_saturated_section/1.

% mode_condition_count(Mode, Count): number of conditions attached to Mode.
#defined mode_condition_count/2.

% mode_condition_usage(Mode, Group, Count): Mode consumes Count occurrences from
% the recall budget of conditional declaration Group.
#defined mode_condition_usage/3.

% condition_group_recall(Group, Recall): maximum total uses of conditions
% expanded from the same conditional declaration group.
#defined condition_group_recall/2.

% Arithmetic schema and eligible operator families.

% mode_arithmetic_operand(Mode, Side, Position): left or right expression
% operand of a recognized three-placeholder arithmetic template.
#defined mode_arithmetic_operand/3.

% mode_arithmetic_result(Mode, Position): result placeholder of that template.
#defined mode_arithmetic_result/2.

% add_mode / mul_mode: Mode is a complete + or * template.
#defined add_mode/1.
#defined mul_mode/1.

% interchangeable_operands(Mode): the two operands of an arithmetic template or
% a simple binary comparison, or the two arguments of a binary atom of plain
% variables, have equal type, direction and label, so swapping them yields
% another template instance. Every orientation choice requires it: a swapped
% literal of a directed or typed template can be illegal.
#defined interchangeable_operands/1.

% div_mode / mod_mode: Mode is a complete / or modulo template. Operand order is
% significant; the flags enable their dedicated semantic views and checks.
#defined div_mode/1.
#defined mod_mode/1.

% abs_mode: Mode is a complete |Left-Right| template.
#defined abs_mode/1.

% Comparison schema.

% comparison_operator(Mode, Operator): Mode is a simple binary comparison whose
% sole operator is one of eq, neq, lt, gt, leq or geq. Complex comparison chains
% deliberately have no fact.
#defined comparison_operator/2.

% numeric_equality_mode(Mode): a positive body equality between two numeric
% placeholders. Only emitted when such an equality exists in the task.
#defined numeric_equality_mode/1.

% numeric_linear_conflict(EqualityMode, ComparisonMode): exact proportional
% homogeneous rows, compared with the same ordered variable bindings and the
% distinctness guard specified by numeric_linear_distinct_mode.
#defined numeric_linear_conflict/2.

% numeric_linear_distinct_mode(EqualityMode): this paired equality requires
% distinct bindings to guarantee that its positive anchor cannot cancel.
#defined numeric_linear_distinct_mode/1.

% nonlinear_builtin_mode(Mode): a selected builtin would prevent the guarded
% all-linear normalization used by numeric_linear_conflict pruning.
#defined nonlinear_builtin_mode/1.

% complex_numeric_builtin_mode(Mode): a body builtin handled by Python's
% ArithmeticSystem that is not a simple comparison of numeric placeholders.
% Emitted alongside numeric_equality_mode; guards its early contradiction check.
#defined complex_numeric_builtin_mode/1.

% strict_comparison_args(Mode, LeftPosition, RightPosition): two adjacent plain
% variable terms of Mode are related by < or > at these flattened positions,
% outside a positive simple comparison whose self bindings policy already rejects.
#defined strict_comparison_args/3.

% Aggregate schema. Condition ids preserve repeated occurrences of the same
% predicate; Position remains the flattened storage position of the mode.

% aggregate_shape(Mode, TupleArity, ConditionCount): source tuple width and
% number of condition occurrences of an aggregate template.
#defined aggregate_shape/3.

% aggregate_has_shorter_mode(Mode): the language bias also declares an aggregate
% of the same function and conditions with one fewer tuple term.
#defined aggregate_has_shorter_mode/1.

% count_aggregate_mode / sum_aggregate_mode: aggregate function of Mode.
#defined count_aggregate_mode/1.
#defined sum_aggregate_mode/1.

% mode_aggregate_tuple_arg(Mode, TuplePosition, Position): variable binding at a
% source tuple position maps to flattened Position.
#defined mode_aggregate_tuple_arg/3.

% aggregate_condition_atom(Mode, Condition, Predicate, Arity): identity and
% arity of one aggregate condition occurrence.
#defined aggregate_condition_atom/4.

% mode_aggregate_condition_arg(Mode, Condition, Argument, Position): one source
% argument of a condition occurrence maps to flattened Position.
#defined mode_aggregate_condition_arg/4.

% interchangeable_condition_args(Mode, Condition, First, Second): the same
% guarantee for two plain-variable arguments, First < Second, of one condition
% atom of an aggregate template.
#defined interchangeable_condition_args/4.

% interchangeable_tuple_args(Mode, First, Second): the same guarantee for two
% tuple positions, First < Second, of an aggregate template.
#defined interchangeable_tuple_args/3.

% mode_aggregate_result_arg(Mode, Position): variable binding of the aggregate
% guard/result maps to flattened Position.
#defined mode_aggregate_result_arg/2.

% General aggregate elements have independent local variable scopes. Guard
% positions remain clause-global; only an equality output produces a binding.
#defined mode_aggregate_element_tuple_arg/4.
#defined aggregate_element_condition_atom/5.
#defined aggregate_element_atom/4.
#defined mode_aggregate_element_condition_arg/5.
#defined mode_aggregate_element_positive_arg/4.
#defined mode_aggregate_guard_arg/2.
#defined mode_aggregate_output_arg/2.

% Clingo-proved local comparison bindings and the inputs each proof needs.
#defined local_comparison_variant/6.
#defined local_comparison_input/6.
#defined local_comparison_output/6.

% Exact #modeh head aggregate elements and their positive local conditions.
#defined head_aggregate_element_arg/2.
#defined head_aggregate_condition_atom/3.
#defined head_aggregate_positive_condition_arg/3.
#defined head_guard_arg/2.

% Predicate invention and signed predicate identity.

% invented_pred(Predicate, Layer): Predicate is invented at dependency Layer;
% it may depend only on permitted background or earlier invented predicates.
#defined invented_pred/2.

% strong_complement_pred(Positive, Negative): ids for p/n and -p/n. This records
% strong negation, not default negation.
#defined strong_complement_pred/2.

% Unary properties proved by Clingo for closed predicates: predicates that no
% learned clause can define, directly or through the background. Each property
% holds in the background plus every example context separately. Every argument
% is a signed Predicate id. Absence means "not proved", not that the
% mathematical property is false.

% symmetric_pred: p(X,Y) entails p(Y,X).
#defined symmetric_pred/1.
% asymmetric_pred: p(X,Y) excludes p(Y,X).
#defined asymmetric_pred/1.
% antisymmetric_pred: p(X,Y) and p(Y,X) force X=Y.
#defined antisymmetric_pred/1.
% acyclic_pred: no directed cycle is allowed in the relation.
#defined acyclic_pred/1.
% reflexive_pred: p(X,X) holds for every X in the field of p (domain field(p)).
#defined reflexive_pred/1.
% strict_order_pred: the relation is an irreflexive transitive order.
#defined strict_order_pred/1.
% total_order_pred: the relation is a total order on its field (domain field(p)).
#defined total_order_pred/1.
% transitive_pred: p(X,Y) and p(Y,Z) entail p(X,Z).
#defined transitive_pred/1.
% universal_pred: p contains every tuple of the product of its argument values
% (domain universal(p)).
#defined universal_pred/1.
% empty_pred: p has no tuples in the analyzed closed-world relation.
#defined empty_pred/1.

% Relations between predicates proved from background rules or ground evidence.

% inverse_pred(Left, Right): Left(X,Y) is equivalent to Right(Y,X).
#defined inverse_pred/2.

% implies_pred(Source, Target): every Source tuple is a Target tuple.
#defined implies_pred/2.

% equivalent_pred(Left, Right): both predicates contain the same tuples.
#defined equivalent_pred/2.

% mutex_pred(Left, Right): the predicates cannot hold for the same full tuple.
#defined mutex_pred/2.

% complement_pred(Left, Right): the predicates are disjoint and their union is
% the product of its argument values (domain complement(Left, Right)).
#defined complement_pred/2.

% partition_pred(Group, Predicate): predicates sharing Group are pairwise
% disjoint and their union is the product of its argument values (domain
% partition(Group)).
#defined partition_pred/2.

% domain_cover(Domain, Position, Predicate, Argument): every value of the
% closed Predicate at source Argument lies inside Position of Domain, one of
% field(p), universal(p), complement(p,q) or partition(Group). Domain-relative
% pruning applies only to variables bound at such arguments.
#defined domain_cover/4.

% disjoint_arg(Left, LeftArg, Right, RightArg): the projections at the specified
% source argument positions have disjoint observed values.
#defined disjoint_arg/4.

% tuple_mutex_pred(Left, Right, Mapping): Left and Right are mutually exclusive
% after aligning a projection identified by Mapping. Predicate ids retain
% their signs; sharing Mapping never creates another predicate pair.
#defined tuple_mutex_pred/3.

% tuple_mutex_arg(Mapping, RightArg, LeftArg): one argument alignment belonging
% to a tuple-mutex Mapping. Python emits each complete position mapping once;
% identical mappings may serve several tuple_mutex_pred pairs.
#defined tuple_mutex_arg/3.

% project_implies_pred(Source, Target, Projection): projecting Source according
% to Projection entails Target.
#defined project_implies_pred/3.

% project_arg(Projection, TargetArg, SourceArg): argument correspondence for one
% projected implication.
#defined project_arg/3.

% Properties of argument positions.

% Conservative positive occurrences by signed predicate and shared recall groups.
#defined positive_body_capacity/2.

% arg_equal_pred(Predicate, LeftArg, RightArg): the two positions are always
% equal in the analyzed relation.
#defined arg_equal_pred/3.

% arg_distinct_pred(Predicate, LeftArg, RightArg): the two positions are always
% different in the analyzed relation.
#defined arg_distinct_pred/3.

% functional_pred(Predicate, InputArg, OutputArg): one input position
% functionally determines one output position.
#defined functional_pred/3.

% functional_set_pred(Predicate, Dependency, OutputArg): Dependency identifies
% a set of input positions that jointly determines OutputArg.
#defined functional_set_pred/3.

% functional_set_arg(Dependency, InputArg): one determining position of a
% functional-set Dependency.
#defined functional_set_arg/2.

% key_pred(Predicate, Key): Key identifies a set of positions that uniquely
% determines a tuple of Predicate.
#defined key_pred/2.

% key_arg(Key, Argument): one source argument position belonging to Key.
#defined key_arg/2.

% cardinality_upper_pred(Predicate, Upper): proved upper bound on the number of
% tuples in Predicate over the analyzed task domain.
#defined cardinality_upper_pred/2.

#defined nominal_bindings/0.
#defined connected_bindings/0.
#defined binding_type/1.
#defined body_counts/0.
#defined canonical_components/0.
#defined canonical_strict_mode/2.
