% Closed-world projected implication property.
%
% Python emits project_implies_pred(Pred0,Pred1,Projection) plus project_arg
% facts when Pred0 implies Pred1 after mapping source arguments to target
% arguments. Example: edge(X,Y) may imply node(X) via projection target arg 0
% from source arg 0.
%
% Shared atom shapes used here:
% - project_implies_pred(Pred0,Pred1,Projection): Pred0 implies Pred1 under
%   Projection id.
% - project_arg(Projection,TargetArg,SourceArg): target argument TargetArg of
%   Pred1 maps to source argument SourceArg of Pred0.
% - normal_literal(Section,Slot,Mode,Pred,Arity): selected normal literal.
% - positive_body_literal/4, negative_body_literal/4, head_literal/4: aliases.
% - var_at(Section,Slot,Arg,Var): variable assignment.

#defined project_implies_pred/3.
#defined project_arg/3.

% Rule: projected variables differ at one mapped argument.
% Section0/Slot0 is source literal, Section1/Slot1 is target literal.
% Projection is projection id. TargetArg is target predicate argument index.
% SourceArg is source predicate argument index. SourceVar and TargetVar are the
% variables at those positions. Difference means projection does not match.
project_vars_differ(Section0,Slot0,Section1,Slot1,Projection):-
    project_arg(Projection,TargetArg,SourceArg),
    var_at(Section0,Slot0,SourceArg,SourceVar),
    var_at(Section1,Slot1,TargetArg,TargetVar),
    SourceVar != TargetVar.

% Rule: projected variables match for a source/target literal pair.
% Section0/Slot0 selects Pred0, Section1/Slot1 selects Pred1. project_implies_pred
% supplies Projection. If no project_vars_differ fact exists, every mapped target
% argument uses the corresponding source variable.
project_vars_match(Section0,Slot0,Section1,Slot1,Projection):-
    normal_literal(Section0,Slot0,_,Pred0,_),
    normal_literal(Section1,Slot1,_,Pred1,_),
    project_implies_pred(Pred0,Pred1,Projection),
    not project_vars_differ(Section0,Slot0,Section1,Slot1,Projection).

% Constraint: reject redundant positive projected implication target.
% Slot0 is positive source Pred0. Slot1 is positive target Pred1. Projection
% variables match, so Pred1 is implied by Pred0 and adds no body filtering.
:- positive_body_literal(Slot0,_,Pred0,_),
    positive_body_literal(Slot1,_,Pred1,_),
    Slot0 != Slot1,
    project_implies_pred(Pred0,Pred1,Projection),
    project_vars_match(body,Slot0,body,Slot1,Projection).

% Constraint: reject negative target contradicted by projected implication.
% Slot0 is positive source Pred0. Slot1 is not Pred1. Projection variables
% match, so Pred0 implies the denied target tuple.
:- positive_body_literal(Slot0,_,Pred0,_),
    negative_body_literal(Slot1,_,Pred1,_),
    Slot0 != Slot1,
    project_implies_pred(Pred0,Pred1,Projection),
    project_vars_match(body,Slot0,body,Slot1,Projection).

% Constraint: reject head target already implied by positive body source.
% Slot0 is positive body source Pred0. Slot1 is head target Pred1. Projection
% variables match, making the rule tautological/redundant.
:- positive_body_literal(Slot0,_,Pred0,_),
    head_literal(Slot1,_,Pred1,_),
    project_implies_pred(Pred0,Pred1,Projection),
    project_vars_match(body,Slot0,head,Slot1,Projection).
