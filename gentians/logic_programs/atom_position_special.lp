atom_pos(Pos):-
    pos(Pos),
    not non_atom_pos(Pos).

:- not atom_pos(_).

