{heur}.
possible_head(I, heur__(H)) :- possible_head(I, H), heur, #false : H = heur__(_).
possible_body(I, H) :- possible_head(I, H), heur, #false : H = heur__(_).
at(heur__(H), I, V) :- possible_head(_, heur__(H)), at(H, I, V).
mapping(I, heur__(A), heur__(M)) :- mapping(I, A, M), possible_head(_, heur__(A)).

head(heur__(H)) : possible_head(_, heur__(H)) :- heur.
body(H) :- head(heur__(H)), heur.
:- heur, constraint.
cost(1, x) :- heur.
:- heur, #count { X : body(X) } != 1.

