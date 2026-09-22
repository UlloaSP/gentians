% Prune arithmetic using the observed numeric-domain facts supplied by Python.
% Propagate positive values through addition, multiplication and comparisons;
% positive addition induces strict operand/result order. Domain-specific bounds
% also reject impossible modulo, multiplication and integer-division relations.

#defined numeric_domain_nonnegative/0.
#defined numeric_domain_positive/0.
#defined add_mode/1.
#defined mul_mode/1.
#defined div_mode/1.
#defined mod_mode/1.

domain_numeric_arg(Pred,Arity,Arg):-
    mode(_,Mode,Pred,Arity,_),
    normal_mode(Mode),
    mode_arg_type(Mode,Arg,numeric).

numeric_domain_nonnegative:- numeric_domain_positive.

domain_constrained_var(Var):-
    selected(Section,Slot,Mode),
    mode(Section,Mode,Pred,Arity,_),
    domain_numeric_arg(Pred,Arity,Arg),
    var_at(Section,Slot,Arg,Var).

positive_value_var(Var):-
    numeric_domain_positive,
    domain_constrained_var(Var).

positive_value_var(Result):-
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Left),
    positive_value_var(Right).

% If Value+Value=Result and Result is positive, Value is positive too.

positive_value_var(Value):-
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Value),
    var_at(body,Slot,1,Value),
    var_at(body,Slot,2,Result),
    positive_value_var(Result).

positive_value_var(Result):-
    selected(body,Slot,Mode),
    mul_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Left),
    positive_value_var(Right).

positive_value_var(Greater):- lt_vars(Smaller,Greater), positive_value_var(Smaller).

positive_value_var(Greater):- leq_vars(Smaller,Greater), positive_value_var(Smaller).

lt_value_vars(Left,Right):- lt_vars(Left,Right).

lt_value_vars(Left,Result):-
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Right).

lt_value_vars(Right,Result):-
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Left).

% Propagated strict order rejects cycles even across several arithmetic literals.

lt_value_vars(Left,Right):- lt_value_vars(Left,Middle), lt_value_vars(Middle,Right).

:- lt_value_vars(Var,Var).

:- numeric_domain_nonnegative,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Left),
    domain_constrained_var(Result),
    lt_vars(Result,Left).

:- numeric_domain_nonnegative,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Right),
    domain_constrained_var(Result),
    lt_vars(Result,Right).

:- numeric_domain_positive,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Left),
    domain_constrained_var(Right),
    domain_constrained_var(Result),
    leq_vars(Result,Left).

:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Right),
    lt_vars(Result,Left).

:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Right),
    leq_vars(Result,Left).

:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Right),
    lt_vars(Left,Result).

:- numeric_domain_positive,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Left),
    domain_constrained_var(Right),
    domain_constrained_var(Result),
    leq_vars(Result,Right).

:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Left),
    lt_vars(Result,Right).

:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Left),
    leq_vars(Result,Right).

:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Left),
    lt_vars(Right,Result).

:- numeric_domain_positive,
    selected(body,Slot,Mode),
    mod_mode(Mode),
    var_at(body,Slot,1,Divisor),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Divisor),
    domain_constrained_var(Result),
    leq_vars(Divisor,Result).

:- numeric_domain_positive,
    selected(body,Slot,Mode),
    mul_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Left),
    domain_constrained_var(Right),
    domain_constrained_var(Result),
    lt_vars(Result,Left).

:- numeric_domain_positive,
    selected(body,Slot,Mode),
    mul_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Left),
    domain_constrained_var(Right),
    domain_constrained_var(Result),
    lt_vars(Result,Right).

:- numeric_domain_positive,
    selected(body,Slot,Mode),
    div_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Left),
    domain_constrained_var(Right),
    domain_constrained_var(Result),
    lt_vars(Left,Result).
