% Keep learnable facts but reject the completely empty clause.
% prune_optional_constraints is emitted only when the task proof establishes
% that a perfect nonempty hypothesis needs a learned head. Uncertain tasks keep
% the headless branch. Attached conditions share the ordinary body budget.

#defined prune_optional_constraints/0.

:- body_count(Body),
    selected_condition_count(Conditions),
    max_body(Max),
    Body + Conditions > Max.

:- prune_optional_constraints, not selected_slot(head,_).

:- not selected_slot(head,_), not selected_slot(body,_).
