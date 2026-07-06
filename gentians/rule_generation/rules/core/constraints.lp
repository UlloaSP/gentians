% Clause-shape constraints.
%
% This file enforces basic syntactic policy for generated clauses: every clause
% must have a body, and headless constraints must contain at least two body
% literals.
%
% Shared atom shapes used here:
% - selected_slot(Section,Slot): defined in core/slots.lp. Section is head/body;
%   Slot is an occupied slot id.

% Constraint: reject empty bodies.
% A generated clause with no selected body slot has no evidence condition and
% is not useful in this hypothesis space.
:- not selected_slot(body,_).

% Constraint: reject unary headless constraints.
% If there is no head, require at least two body slots. This avoids constraints
% that merely ban a single literal and usually erase all examples too broadly.
:- not selected_slot(head,_), #count{Slot : selected_slot(body,Slot)} < 2.
