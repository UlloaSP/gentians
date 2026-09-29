% Derive sign and strict value order from selected arithmetic and the
% per-argument evidence Python proves with Clingo. positive_arg(Pred, Arg) and
% nonnegative_arg(Pred, Arg) hold when every value that argument of a closed
% predicate takes, in every model of every context, is an integer > 0 or >= 0.
% Only a positive body literal grounds its variable to such a value: a head
% atom, a negated literal or a learned predicate says nothing about it.
% inferred_lt is a transitive closure; selected_lt continues to mean an
% explicit comparison literal.


positive_value(Var) :-
    positive_body_literal(Slot, _, Pred, _),
    positive_arg(Pred, Arg),
    var_at(body, Slot, Arg, Var).

nonnegative_value(Var) :-
    positive_body_literal(Slot, _, Pred, _),
    nonnegative_arg(Pred, Arg),
    var_at(body, Slot, Arg, Var).

nonnegative_value(Var) :- positive_value(Var).

positive_value(Result) :-
    addition(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right).

positive_value(Value) :-
    addition(Slot, Value, Value, Result),
    positive_value(Result).

positive_value(Result) :-
    multiplication(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right).

positive_value(Greater) :- selected_lt(Smaller, Greater), positive_value(Smaller).

positive_value(Greater) :- selected_leq(Smaller, Greater), positive_value(Smaller).

inferred_lt(Left, Right) :- selected_lt(Left, Right).

inferred_lt(Left, Result) :-
    addition(Slot, Left, Right, Result),
    positive_value(Right).

inferred_lt(Right, Result) :-
    addition(Slot, Left, Right, Result),
    positive_value(Left).

inferred_lt(Left, Right) :- inferred_lt(Left, Middle), inferred_lt(Middle, Right).
