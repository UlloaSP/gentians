% Prune self comparisons, contradictions and redundant comparison combinations.
% Prefer a strict comparison to <= plus != only if the bias offers a strict
% operator. Transitive shortcuts are tested against the selected relations;
% adding inferred edges here would erase the distinction from explicit literals.

:- selected(body,Slot,Mode),
    strict_comparison_args(Mode,LeftArg,RightArg),
    var_at(body,Slot,LeftArg,Var),
    var_at(body,Slot,RightArg,Var).

:- selected(body,Slot,Mode),
    simple_comparison_mode(Mode),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).

:- selected(body,Slot,Mode),
    neq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

:- lt_vars(Left,Right), lt_vars(Right,Left).

:- lt_vars(Left,Right), leq_vars(Right,Left).

:- lt_vars(Left,Right), leq_vars(Left,Right).

:- leq_vars(Left,Right), leq_vars(Right,Left).

:- lt_vars(Left,Right), neq_vars(Left,Right).

:- strict_comparison_available, leq_vars(Left,Right), neq_vars(Left,Right).

:- lt_vars(Left,Right), lt_vars(Left,Middle), lt_vars(Middle,Right).

:- lt_vars(Left,Right), lt_vars(Left,Middle), leq_vars(Middle,Right).

:- lt_vars(Left,Right), leq_vars(Left,Middle), lt_vars(Middle,Right).

:- leq_vars(Left,Right), lt_vars(Left,Middle), lt_vars(Middle,Right).

:- leq_vars(Left,Right), lt_vars(Left,Middle), leq_vars(Middle,Right).

:- leq_vars(Left,Right), leq_vars(Left,Middle), lt_vars(Middle,Right).

:- leq_vars(Left,Right), leq_vars(Left,Middle), leq_vars(Middle,Right).

:- neq_vars(Left,Right), lt_vars(Left,Middle), lt_vars(Middle,Right).

:- neq_vars(Left,Right), lt_vars(Left,Middle), leq_vars(Middle,Right).

:- neq_vars(Left,Right), leq_vars(Left,Middle), lt_vars(Middle,Right).
