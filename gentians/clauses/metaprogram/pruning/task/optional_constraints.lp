% Task-relative pruning, not ASP equivalence. Python proves a learned head is
% necessary for a perfect hypothesis before emitting prune_optional_constraints.

#defined prune_optional_constraints/0.

:- prune_optional_constraints, not selected_slot(head, _).
