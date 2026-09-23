% Classify selected literals for safety and pruning consumers.
% Normal literals exclude comparisons, arithmetic, aggregates and conditionals.
% Head classification also includes conclusions of conditional head elements.


positive_mode(Mode) :-
    mode_kind(Mode, _),
    not negative_mode(Mode).

normal_mode(Mode) :- mode_kind(Mode, normal).

conditional_mode(Mode) :- mode_kind(Mode, conditional).
head_aggregate_mode(Mode) :- mode_kind(Mode, head_aggregate).

normal_literal(Section, Slot, Mode, Pred, Arity) :-
    selected(Section, Slot, Mode),
    normal_mode(Mode),
    mode_atom(Mode, Pred, Arity).

positive_normal_literal(Section, Slot, Mode, Pred, Arity) :-
    normal_literal(Section, Slot, Mode, Pred, Arity),
    positive_mode(Mode).

negative_normal_literal(Section, Slot, Mode, Pred, Arity) :-
    normal_literal(Section, Slot, Mode, Pred, Arity),
    negative_mode(Mode).

positive_body_literal(Slot, Mode, Pred, Arity) :-
    positive_normal_literal(body, Slot, Mode, Pred, Arity).

negative_body_literal(Slot, Mode, Pred, Arity) :-
    negative_normal_literal(body, Slot, Mode, Pred, Arity).

head_literal(Slot, Mode, Pred, Arity) :-
    positive_normal_literal(head, Slot, Mode, Pred, Arity).

head_literal(Slot, Mode, Pred, Arity) :-
    conditional_head_literal(Slot, Mode, Pred, Arity).

head_literal(Slot, Mode, Pred, Arity) :-
    selected(head, Slot, Mode), head_aggregate_mode(Mode),
    mode_atom(Mode, Pred, Arity).
