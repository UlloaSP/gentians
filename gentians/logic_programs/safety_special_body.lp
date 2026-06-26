v_body(V,P):-
    var_pos(V,P),
    P > VHI,
    last_index_var_in_head(VHI).

