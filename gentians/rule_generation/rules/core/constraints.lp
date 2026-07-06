% Clause-shape constraints.
%
% This file enforces basic syntactic policy for generated clauses: every clause
% must have a body; headless clauses are allowed only when constraints are
% enabled; and headless constraints must contain at least two body literals.
%
% Shared atom shapes used here:
% - constraints_allowed: Python fact emitted only when headless generated
%   constraints are permitted.
% - selected_slot(Section,Slot): defined in core/slots.lp. Section is head/body;
%   Slot is an occupied slot id.

#defined constraints_allowed/0.

% Constraint: reject empty bodies.
% A generated clause with no selected body slot has no evidence condition and
% is not useful in this hypothesis space.
:- not selected_slot(body,_).

% Constraint: reject headless clauses unless constraint generation is enabled.
% selected_slot(head,_) absent means the candidate is an ASP constraint.
% constraints_allowed is controlled by Python capabilities.
:- not selected_slot(head,_), not constraints_allowed.

% Constraint: reject unary headless constraints.
% If there is no head, require at least two body slots. This avoids constraints
% that merely ban a single literal and usually erase all examples too broadly.
:- not selected_slot(head,_), #count{Slot : selected_slot(body,Slot)} < 2.
