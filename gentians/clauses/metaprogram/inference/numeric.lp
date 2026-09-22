% Derive positivity and strict value order from selected arithmetic and the
% numeric-domain evidence supplied by Python. inferred_lt is a transitive
% closure; selected_lt continues to mean an explicit comparison literal.

#defined numeric_domain_nonnegative/0.
#defined numeric_domain_positive/0.
#defined add_mode/1.
#defined mul_mode/1.
#defined div_mode/1.
#defined mod_mode/1.

domain_numeric_arg(Pred, Arity, Arg) :-
    mode(_, Mode, Pred, Arity, _),
    normal_mode(Mode),
    mode_arg_type(Mode, Arg, numeric).

numeric_domain_nonnegative :- numeric_domain_positive.

numeric_argument_var(Var) :-
    selected(Section, Slot, Mode),
    mode(Section, Mode, Pred, Arity, _),
    domain_numeric_arg(Pred, Arity, Arg),
    var_at(Section, Slot, Arg, Var).

positive_value(Var) :-
    numeric_domain_positive,
    numeric_argument_var(Var).

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
