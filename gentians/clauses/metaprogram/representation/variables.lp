% Variable occurrence and repeated-name relations; ids denote syntax, not values.

% DEFINITION, reusable. used_var(Var): Var occurs somewhere in the clause.
%   Var  variable id (rendered V<Var>) held by at least one placeholder.
% Shared because symmetry/variables.lp orders exactly the used ids and
% pruning/policies/singletons.lp inspects each used id once.
used_var(Var) :- var_at(_, _, _, Var).

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
