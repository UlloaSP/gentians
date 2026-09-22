% Clause-wide body budget and exclusion of the completely empty clause.

:- body_count(Body),
    selected_condition_count(Conditions),
    max_body(Max),
    Body + Conditions > Max.

:- not selected_slot(head, _), not selected_slot(body, _).
