cv_body(Var,C):-
    CT = #count{P : v_body(Var,P)},
    CI = #count{P : ignored_body_position(Var,P)},
    var(Var),
    C = CT - CI.

cv_head(Var,C):-
    C = #count{Pos : var_pos(Var,Pos), Pos <= VHI},
    var(Var),
    last_index_var_in_head(VHI).

:- cv_head(Var,CH), cv_body(Var,0), CH > 0.

