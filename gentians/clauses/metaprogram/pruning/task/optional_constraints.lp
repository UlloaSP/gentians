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
