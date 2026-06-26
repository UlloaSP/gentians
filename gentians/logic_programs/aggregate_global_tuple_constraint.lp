not_agg_pos(P):-
    pos(P),
    not aggregate_term_position(_,P),
    not aggregate_atom_position(_,P).

:- not_agg_pos(P),
    var_pos(V,P),
    aggregate_term_position(_,PosTermAgg),
    var_pos(V,PosTermAgg).

