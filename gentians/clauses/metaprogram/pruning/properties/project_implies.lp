% Closed-world projected implication property.
%
% Python emits project_implies_pred(Pred0, Pred1, Projection) plus project_arg
% facts when Pred0 implies Pred1 after mapping source arguments to target
% arguments. Example: edge(X, Y) may imply node(X) via projection target arg 0
% from source arg 0.

#defined project_implies_pred/3.
#defined project_arg/3.

project_vars_differ(Section0, Slot0, Section1, Slot1, Projection) :-
    project_arg(Projection, TargetArg, SourceArg),
    var_at(Section0, Slot0, SourceArg, SourceVar),
    var_at(Section1, Slot1, TargetArg, TargetVar),
    SourceVar != TargetVar.

project_vars_match(Section0, Slot0, Section1, Slot1, Projection) :-
    normal_literal(Section0, Slot0, _, Pred0, _),
    normal_literal(Section1, Slot1, _, Pred1, _),
    project_implies_pred(Pred0, Pred1, Projection),
    not project_vars_differ(Section0, Slot0, Section1, Slot1, Projection).

:- positive_body_literal(Slot0, _, Pred0, _),
    positive_body_literal(Slot1, _, Pred1, _),
    Slot0 != Slot1,
    project_implies_pred(Pred0, Pred1, Projection),
    project_vars_match(body, Slot0, body, Slot1, Projection).

:- positive_body_literal(Slot0, _, Pred0, _),
    negative_body_literal(Slot1, _, Pred1, _),
    Slot0 != Slot1,
    project_implies_pred(Pred0, Pred1, Projection),
    project_vars_match(body, Slot0, body, Slot1, Projection).

:- positive_body_literal(Slot0, _, Pred0, _),
    head_literal(Slot1, _, Pred1, _),
    project_implies_pred(Pred0, Pred1, Projection),
    project_vars_match(body, Slot0, head, Slot1, Projection).
