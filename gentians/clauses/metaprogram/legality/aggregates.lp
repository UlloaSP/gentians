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
