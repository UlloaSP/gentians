% Arithmetic domain pruning.
%
% This file prunes arithmetic/comparison combinations that are impossible given
% numeric domains observed by Python. It uses conservative facts such as
% numeric_domain_nonnegative and numeric_domain_positive to remove candidates
% that would force results outside known numeric argument domains.
%
% Shared atom shapes used here:
% - domain_numeric_arg(Pred,Arity,Arg): derived atom. Normal predicate argument
%   Arg is numeric and domain-constrained by observed facts.
% - zero_not_in_numeric_domain: Python fact or derived atom. Observed numeric domain has no 0.
% - numeric_domain_nonnegative: Python fact. Observed numeric domain values are
%   all >= 0, or derived from numeric_domain_positive.
% - numeric_domain_positive: Python fact. Observed numeric domain values are all
%   > 0.
% - add_mode/mul_mode/div_mode/mod_mode: Python arithmetic facts.
% - selected(Section,Slot,Mode), mode(...), var_at(...): selected literal data.
% - normal_mode(Mode): derived by core/literals.lp for normal predicate modes.
% - mode_arg_type(Mode,Arg,Type): Python fact with non-any declared argument type.
% - lt_vars/2 and leq_vars/2: normalized comparison helpers.

% Optional facts emitted by Python for the observed numeric domain and enabled
% arithmetic operator families.
#defined zero_not_in_numeric_domain/0.
#defined numeric_domain_nonnegative/0.
#defined numeric_domain_positive/0.
#defined add_mode/1.
#defined mul_mode/1.
#defined div_mode/1.
#defined mod_mode/1.

% Rule: normal numeric mode args are numeric-domain predicate args.
% Section/Mode/Pred/Arity identify a normal predicate mode. Arg is a zero-based
% argument declared numeric by mode_arg_type/3. Operators are excluded by
% normal_mode(Mode), so only predicate arguments become domain-constrained.
domain_numeric_arg(Pred,Arity,Arg):-
    mode(_,Mode,Pred,Arity,_),
    normal_mode(Mode),
    mode_arg_type(Mode,Arg,numeric).

% Rule: positive numeric domains are nonnegative.
% A domain where every value is > 0 also satisfies every >= 0 pruning rule.
numeric_domain_nonnegative:- numeric_domain_positive.

% Rule: positive numeric domains exclude zero.
% A domain where every value is > 0 cannot contain 0, so zero-specific pruning
% can consume the weaker zero_not_in_numeric_domain atom.
zero_not_in_numeric_domain:- numeric_domain_positive.

% Rule: mark variables that are used in numeric domain-constrained predicate args.
% Section/Slot/Mode identify any selected literal. Pred/Arity/Arg identify a
% normal predicate argument known numeric by domain_numeric_arg. Var is the
% generated variable placed in that argument.
domain_constrained_var(Var):-
    selected(Section,Slot,Mode),
    mode(Section,Mode,Pred,Arity,_),
    domain_numeric_arg(Pred,Arity,Arg),
    var_at(Section,Slot,Arg,Var).

% Rule: mark variables known to be strictly positive.
% Domain-constrained numeric variables are positive when every observed numeric
% domain value is positive. Addition/multiplication of positive values also
% remains positive, even when the result variable is only used by operators.
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
positive_value_var(Right):- equal_value_vars(Left,Right), positive_value_var(Left).

zero_value_var(Result):-
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    zero_value_var(Left),
    zero_value_var(Right).

zero_value_var(Value):-
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Value),
    var_at(body,Slot,1,Value),
    var_at(body,Slot,2,Result),
    zero_value_var(Result).

zero_value_var(Result):-
    selected(body,Slot,Mode),
    mul_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,2,Result),
    zero_value_var(Left).

zero_value_var(Result):-
    selected(body,Slot,Mode),
    mul_mode(Mode),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    zero_value_var(Right).

zero_value_var(Right):- equal_value_vars(Left,Right), zero_value_var(Left).

equal_value_vars(Right,Left):- equal_value_vars(Left,Right).

% Rule: derive strict order known from comparisons and arithmetic.
lt_value_vars(Left,Right):- lt_vars(Left,Right).
lt_value_vars(Left,Right):- equal_value_vars(Left,Equal), lt_value_vars(Equal,Right).
lt_value_vars(Left,Right):- equal_value_vars(Right,Equal), lt_value_vars(Left,Equal).

% Rule: positive addition makes each operand smaller than the result.
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

lt_value_vars(Left,Right):- lt_value_vars(Left,Middle), lt_value_vars(Middle,Right).

% Constraint: reject variables known as both zero and strictly positive.
:- zero_value_var(Var), positive_value_var(Var).

% Constraint: reject strict-order cycles.
:- lt_value_vars(Var,Var).

% Constraint: reject ordering between values known equal.
:- equal_value_vars(Left,Right), Left != Right.
:- equal_value_vars(Left,Right), lt_vars(Left,Right).
:- equal_value_vars(Left,Right), lt_vars(Right,Left).

% Constraint: reject positive values constrained below or equal to zero.
:- positive_value_var(Positive), zero_value_var(Zero), lt_vars(Positive,Zero).
:- positive_value_var(Positive), zero_value_var(Zero), leq_vars(Positive,Zero).

% Constraint: reject tautological zero/positive comparisons.
% If Zero is known 0 and Positive is known >0, Zero < Positive and
% Zero <= Positive add no filtering power.
:- zero_value_var(Zero), positive_value_var(Positive), lt_vars(Zero,Positive).
:- zero_value_var(Zero), positive_value_var(Positive), leq_vars(Zero,Positive).

% Constraint: reject addition-by-zero equality encodings.
% X+0=Y and 0+X=Y only force X=Y; generated clauses should express that by
% sharing a variable instead of carrying redundant arithmetic.
:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    zero_value_var(Left).

:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,1,Right),
    zero_value_var(Right).

% Constraint: reject multiplication-by-zero encodings.
% 0*X=Y and X*0=Y only force Y=0 once a zero variable already exists.
:- selected(body,Slot,Mode),
    mul_mode(Mode),
    var_at(body,Slot,0,Left),
    zero_value_var(Left).

:- selected(body,Slot,Mode),
    mul_mode(Mode),
    var_at(body,Slot,1,Right),
    zero_value_var(Right).

% Constraint: reject nonnegative addition where Result < Left.
% For nonnegative Right, Left + Right cannot be less than Left. Left and Result
% are checked only when both are domain-constrained numeric variables.
:- numeric_domain_nonnegative,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Left),
    domain_constrained_var(Result),
    lt_vars(Result,Left).

% Constraint: reject nonnegative addition where Result < Right.
% For nonnegative Left, Left + Right cannot be less than Right. Right and Result
% must both be domain-constrained numeric variables.
:- numeric_domain_nonnegative,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Right),
    domain_constrained_var(Result),
    lt_vars(Result,Right).

% Constraint: reject positive addition where Result <= Left.
% If both inputs are positive, Left + Right is strictly greater than Left. This
% rejects candidates also containing Result <= Left.
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

% Constraint: reject comparison already implied by positive addition.
% If Right > 0 then Left < Result follows from Left+Right=Result.
:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Right),
    lt_vars(Left,Result).

% Constraint: reject positive addition where Result <= Right.
% If both inputs are positive, Left + Right is strictly greater than Right.
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

% Constraint: reject comparison already implied by positive addition.
% If Left > 0 then Right < Result follows from Left+Right=Result.
:- selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    positive_value_var(Left),
    lt_vars(Right,Result).

% Constraint: reject modulo result greater than or equal to positive divisor.
% For positive Divisor, Result from Value \ Divisor must satisfy Result < Divisor.
% leq_vars(Divisor,Result) contradicts that.
:- numeric_domain_positive,
    selected(body,Slot,Mode),
    mod_mode(Mode),
    var_at(body,Slot,1,Divisor),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Divisor),
    domain_constrained_var(Result),
    leq_vars(Divisor,Result).

% Constraint: reject positive multiplication where Result < Left.
% With positive Right, Left*Right cannot be less than Left when all variables
% are constrained to the positive numeric domain.
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

% Constraint: reject positive multiplication where Result < Right.
% With positive Left, Left*Right cannot be less than Right under positive
% numeric domain constraints.
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

% Constraint: reject positive division where Result exceeds numerator.
% For positive Right, integer division Left/Right cannot be greater than Left
% in the positive numeric domain. lt_vars(Left,Result) contradicts that.
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
