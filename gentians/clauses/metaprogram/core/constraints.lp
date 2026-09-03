% Clause-shape constraints.
%
% This file enforces basic syntactic policy for generated clauses. Facts and
% other rules with an empty body are valid when their head is ASP-safe. The
% completely empty clause is not a rule and remains forbidden.
%
% Shared atom shapes used here:
% - selected_slot(Section,Slot): defined in core/slots.lp. Section is head/body;
%   Slot is an occupied slot id.
% - body_count(Count): defined in core/limits.lp. Count is selected body slots.

#defined invented_pred/2.
#defined aggregate_condition_atom/5.

% Constraint: reject the empty clause while permitting learnable facts.
:- not selected_slot(head,_), not selected_slot(body,_).

% Invented predicates form ordered, acyclic definition layers. An invented
% head may depend only on background predicates or invented predicates declared
% in earlier layers.
:- head_literal(_,_,HeadPred,_),
    invented_pred(HeadPred,HeadLayer),
    positive_body_literal(_,_,BodyPred,_),
    invented_pred(BodyPred,BodyLayer),
    BodyLayer >= HeadLayer.
:- head_literal(_,_,HeadPred,_),
    invented_pred(HeadPred,HeadLayer),
    conditional_dependency(_,_,BodyPred),
    invented_pred(BodyPred,BodyLayer),
    BodyLayer >= HeadLayer.
:- head_literal(_,_,HeadPred,_),
    invented_pred(HeadPred,HeadLayer),
    selected(body,_,Mode),
    aggregate_condition_atom(Mode,_,BodyPred,_,_),
    invented_pred(BodyPred,BodyLayer),
    BodyLayer >= HeadLayer.

% A definition cannot call an ordinary learnable predicate. Otherwise an
% invented helper and the target can form an indirect cycle.
:- head_literal(_,_,HeadPred,_),
    invented_pred(HeadPred,_),
    normal_literal(body,_,_,BodyPred,_),
    mode(head,_,BodyPred,_,_),
    not invented_pred(BodyPred,_).
:- head_literal(_,_,HeadPred,_),
    invented_pred(HeadPred,_),
    conditional_dependency(_,_,BodyPred),
    mode(head,_,BodyPred,_,_),
    not invented_pred(BodyPred,_).
:- head_literal(_,_,HeadPred,_),
    invented_pred(HeadPred,_),
    selected(body,_,Mode),
    aggregate_condition_atom(Mode,_,BodyPred,_,_),
    mode(head,_,BodyPred,_,_),
    not invented_pred(BodyPred,_).

% Constraints cannot consume invented predicates: they do not contribute to
% defining or using a learned target and multiply dependency-closed programs.
:- not selected_slot(head,_),
    normal_literal(body,_,_,Pred,_),
    invented_pred(Pred,_).
:- not selected_slot(head,_),
    conditional_dependency(body,_,Pred),
    invented_pred(Pred,_).
:- not selected_slot(head,_),
    selected(body,_,Mode),
    aggregate_condition_atom(Mode,_,Pred,_,_),
    invented_pred(Pred,_).
