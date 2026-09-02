% Stable read-only projection for explicit #bias programs.

#defined predicate_symbol/3.

selected_atom(Section,Slot,Name,Arity,Polarity):-
    normal_literal(Section,Slot,Mode,Pred,Arity),
    predicate_symbol(Pred,Name,Arity),
    positive_mode(Mode),
    Polarity = positive.

selected_atom(Section,Slot,Name,Arity,Polarity):-
    normal_literal(Section,Slot,Mode,Pred,Arity),
    predicate_symbol(Pred,Name,Arity),
    negative_mode(Mode),
    Polarity = negative.

selected_atom(Section,Slot,Name,Arity,Polarity):-
    selected(Section,Slot,Mode),
    conditional_mode(Mode,Pred,Arity),
    predicate_symbol(Pred,Name,Arity),
    positive_mode(Mode),
    Polarity = positive.

selected_atom(Section,Slot,Name,Arity,Polarity):-
    selected(Section,Slot,Mode),
    conditional_mode(Mode,Pred,Arity),
    predicate_symbol(Pred,Name,Arity),
    negative_mode(Mode),
    Polarity = negative.
