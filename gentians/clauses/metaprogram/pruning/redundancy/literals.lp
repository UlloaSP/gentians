% Reject repeated literals of the same polarity within a section.
% Equal modes are contiguous and tuple-sorted, so adjacent checks cover repeats;
% different normal modes still require cross-slot comparisons. Opposite body
% polarities and a head/body match are handled by tautologies.lp.

same_normal_literal(Section, Slot0, Section, Slot1) :-
    positive_normal_literal(Section, Slot0, Mode0, Pred, Arity),
    positive_normal_literal(Section, Slot1, Mode1, Pred, Arity),
    Slot0 < Slot1,
    Mode0 != Mode1,
    same_term_bindings(Section, Slot0, Section, Slot1).

same_normal_literal(body, Slot0, body, Slot1) :-
    negative_body_literal(Slot0, Mode0, Pred, Arity),
    negative_body_literal(Slot1, Mode1, Pred, Arity),
    Slot0 < Slot1,
    Mode0 != Mode1,
    same_term_bindings(body, Slot0, body, Slot1).

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
