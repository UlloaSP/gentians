% Global literal-count limit.
%
% This file counts occupied head/body slots and rejects clauses whose total
% number of literals is greater than max_depth/1.
%
% Shared atom shapes used here:
% - max_depth(Max): Python fact. Max is the largest allowed Head+Body literal
%   count for one generated clause.
% - selected_slot(Section,Slot): defined in core/slots.lp. Section is head/body;
%   Slot is an occupied slot id.

% Python fact contract:
% - max_depth(Max): emitted once by Python from args.max_depth. Max is maximum
%   total selected head plus body literals allowed in one candidate clause.
% Python fact detail: max_depth(Max) comes from args.max_depth; Max bounds total selected head plus body literals.
#defined max_depth/1.

% Rule: count selected head slots.
% Count is the number of distinct Slot values where selected_slot(head,Slot)
% holds. This equals number of generated head literals.
head_count(Count):- Count = #count{Slot : selected_slot(head,Slot)}.

% Rule: count selected body slots.
% Count is the number of distinct Slot values where selected_slot(body,Slot)
% holds. This equals number of generated body literals.
body_count(Count):- Count = #count{Slot : selected_slot(body,Slot)}.

% Constraint: reject clauses longer than max_depth.
% Max is max_depth. Head is head_count. Body is body_count. A candidate with
% Head + Body > Max exceeds the configured search depth.
:- max_depth(Max), head_count(Head), body_count(Body), Head + Body > Max.
