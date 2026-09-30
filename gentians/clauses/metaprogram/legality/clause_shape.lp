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
