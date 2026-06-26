ignored_body_position(V,P):-
    v_body(V,P),
    aggregate_term_position(_,P).

ignored_body_position(V,P):-
    v_body(V,P),
    aggregate_atom_position(_,P).

