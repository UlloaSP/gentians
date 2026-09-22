% A reflexive self-pair is redundant positively only if another positive body
% literal still binds its variable. A negative self-pair is always impossible.


:- positive_body_literal(Slot, _, Pred, 2),
    reflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var),
    positive_body_var_outside_slot(Slot, Var).

:- negative_body_literal(Slot, _, Pred, 2),
    reflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var).
