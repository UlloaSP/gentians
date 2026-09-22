% Reject repeated literals with the same predicate/mode and recursive terms.
% Equal modes are contiguous and tuple-sorted, so adjacent checks cover repeats;
% different normal modes still require cross-slot comparisons.

same_normal_literal(Section0, Slot0, Section1, Slot1) :-
    normal_literal(Section0, Slot0, Mode0, Pred, Arity),
    normal_literal(Section1, Slot1, Mode1, Pred, Arity),
    section_order(Section0, Order0),
    section_order(Section1, Order1),
    (Order0, Slot0) < (Order1, Slot1),
    Mode0 != Mode1,
    same_term_bindings(Section0, Slot0, Section1, Slot1).

same_normal_literal(Section, Slot0, Section, Slot1) :-
    normal_literal(Section, Slot0, Mode, Pred, Arity),
    normal_literal(Section, Slot1, Mode, Pred, Arity),
    Slot1 = Slot0 + 1,
    same_term_bindings(Section, Slot0, Section, Slot1).

:- same_normal_literal(Section0, Slot0, Section1, Slot1).

same_mode_literal(body, Slot0, body, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    not normal_mode(Mode),
    Slot1 = Slot0 + 1,
    same_term_bindings(body, Slot0, body, Slot1).

:- same_mode_literal(Section0, Slot0, Section1, Slot1).
