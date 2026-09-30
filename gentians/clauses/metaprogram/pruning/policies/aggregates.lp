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
