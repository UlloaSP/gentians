% Choose one slot encoding: no gaps, nondecreasing modes, sorted equal-mode tuples.
% Equal modes are contiguous; adjacent tuple checks therefore suffice.
% The decoder and duplicate checks rely on these ordering invariants.

:- selected_slot(Section,Slot), Slot > 0, not selected_slot(Section,Slot-1).

:- selected(Section,Slot0,Mode0), selected(Section,Slot1,Mode1), Slot0 < Slot1, Mode0 > Mode1.

same_mode_tuple_gt(Section,Slot0,Slot1):-
    selected(Section,Slot0,Mode),
    selected(Section,Slot1,Mode),
    Slot1 = Slot0 + 1,
    mode_variable_arg(Mode,Arg),
    var_at(Section,Slot0,Arg,Left),
    var_at(Section,Slot1,Arg,Right),
    Left > Right,
    Before = #count{Prev : mode_variable_arg(Mode,Prev), Prev < Arg},
    Before = #count{
        Prev : mode_variable_arg(Mode,Prev), Prev < Arg,
        var_at(Section,Slot0,Prev,Same),
        var_at(Section,Slot1,Prev,Same)
    }.

:- same_mode_tuple_gt(Section,Slot0,Slot1).
