same_occurrence(Id,Occurrence):- same_pos(Id,Occurrence,_,_).
same_arity(Id,Occurrence,N):-
    same_occurrence(Id,Occurrence),
    N = #count{Argument : same_pos(Id,Occurrence,Argument,_)}.

same_argument_equal(Id,OccurrenceA,OccurrenceB,Argument):-
    same_pos(Id,OccurrenceA,Argument,PositionA),
    same_pos(Id,OccurrenceB,Argument,PositionB),
    var_pos(Var,PositionA),
    var_pos(Var,PositionB).

equal:-
    same_occurrence(Id,OccurrenceA),
    same_occurrence(Id,OccurrenceB),
    OccurrenceA < OccurrenceB,
    same_arity(Id,OccurrenceA,N),
    N = #count{Argument : same_argument_equal(Id,OccurrenceA,OccurrenceB,Argument)}.

:- equal.
