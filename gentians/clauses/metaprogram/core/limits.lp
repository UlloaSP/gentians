% Selected literal counts.
%
% This file counts occupied head/body slots for other shape constraints.
%
% Shared atom shapes used here:
% - selected_slot(Section,Slot): defined in core/slots.lp. Section is head/body;
%   Slot is an occupied slot id.

% Rule: count selected head slots.
% Count is the number of distinct Slot values where selected_slot(head,Slot)
% holds. This equals number of generated head literals.
head_count(Count):- Count = #count{Slot : selected_slot(head,Slot)}.

% Rule: count selected body slots.
% Count is the number of distinct Slot values where selected_slot(body,Slot)
% holds. This equals number of generated body literals.
body_count(Count):- Count = #count{Slot : selected_slot(body,Slot)}.

% Optional enumeration order. Assumptions select one exact size per solve;
% every legal size remains available. Attached conditions consume body budget.
#defined enumerate_by_size/0.
clause_body_size(Body+Conditions):-
    enumerate_by_size, body_count(Body), selected_condition_count(Conditions).
