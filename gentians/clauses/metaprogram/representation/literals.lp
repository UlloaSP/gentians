% Classify selected literals for safety and pruning consumers.
% Normal literals exclude comparisons, arithmetic, aggregates and conditionals.
% Head classification also includes conclusions of conditional head elements.

#defined mode/5.
#defined negative_mode/1.

positive_mode(Mode) :-
    mode(_, Mode, _, _, _),
    not negative_mode(Mode).

non_normal_mode(Mode) :- comparison_mode(Mode).

non_normal_mode(Mode) :- arithmetic_mode(Mode).

non_normal_mode(Mode) :- aggregate_mode(Mode, _, _).

non_normal_mode(Mode) :- conditional_mode(Mode, _, _).

normal_mode(Mode) :-
    mode(_, Mode, _, _, _),
    not non_normal_mode(Mode).

normal_literal(Section, Slot, Mode, Pred, Arity) :-
    selected(Section, Slot, Mode),
    normal_mode(Mode),
    mode(Section, Mode, Pred, Arity, _).

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
