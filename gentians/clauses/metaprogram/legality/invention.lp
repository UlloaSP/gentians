% Invented definitions use earlier invention layers or background predicates.
% Calling ordinary learnable predicates could introduce indirect cycles.
% Headless clauses cannot consume invented predicates under this language policy.
% Apply each restriction to ordinary, conditional and aggregate dependencies.


:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, HeadLayer),
    positive_body_literal(_, _, BodyPred, _),
    invented_pred(BodyPred, BodyLayer),
    BodyLayer >= HeadLayer.

:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, HeadLayer),
    conditional_dependency(_, _, BodyPred),
    invented_pred(BodyPred, BodyLayer),
    BodyLayer >= HeadLayer.

:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, HeadLayer),
    selected(body, _, Mode),
    aggregate_condition_atom(Mode, _, BodyPred, _),
    invented_pred(BodyPred, BodyLayer),
    BodyLayer >= HeadLayer.

:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, _),
    normal_literal(body, _, _, BodyPred, _),
    mode_section(HeadMode, head), mode_atom(HeadMode, BodyPred, _),
    not invented_pred(BodyPred, _).

:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, _),
    conditional_dependency(_, _, BodyPred),
    mode_section(HeadMode, head), mode_atom(HeadMode, BodyPred, _),
    not invented_pred(BodyPred, _).

:- head_literal(_, _, HeadPred, _),
    invented_pred(HeadPred, _),
    selected(body, _, Mode),
    aggregate_condition_atom(Mode, _, BodyPred, _),
    mode_section(HeadMode, head), mode_atom(HeadMode, BodyPred, _),
    not invented_pred(BodyPred, _).

:- not selected_slot(head, _),
    normal_literal(body, _, _, Pred, _),
    invented_pred(Pred, _).

:- not selected_slot(head, _),
    conditional_dependency(body, _, Pred),
    invented_pred(Pred, _).

:- not selected_slot(head, _),
    selected(body, _, Mode),
    aggregate_condition_atom(Mode, _, Pred, _),
    invented_pred(Pred, _).
