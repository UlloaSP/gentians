% Arithmetic domain pruning.
%
% This file prunes arithmetic/comparison combinations that are impossible given
% numeric domains observed by Python. It uses conservative facts such as
% numeric_domain_nonnegative and numeric_domain_positive to remove candidates
% that would force results outside known numeric argument domains.
%
% Shared atom shapes used here:
% - domain_numeric_arg(Pred,Arity,Arg): Python fact. Normal predicate argument
%   Arg is numeric and domain-constrained by observed facts.
% - zero_not_in_numeric_domain: Python fact. Observed numeric domain has no 0.
% - numeric_domain_nonnegative: Python fact. Observed numeric domain values are
%   all >= 0.
% - numeric_domain_positive: Python fact. Observed numeric domain values are all
%   > 0.
% - add_mode/sub_mode/mul_mode/div_mode/mod_mode: Python arithmetic facts.
% - selected(Section,Slot,Mode), mode(...), var_at(...): selected literal data.
% - lt_vars/2 and leq_vars/2: normalized comparison helpers.

% Python fact contract:
% - domain_numeric_arg(Pred,Arity,Arg): emitted by Python for normal predicate
%   positions known numeric from language/evidence. Pred is predicate id, Arity
%   predicate arity, Arg zero-based argument index.
% - zero_not_in_numeric_domain: emitted by Python when observed numeric domain
%   does not contain 0.
% - numeric_domain_nonnegative: emitted by Python when observed numeric domain
%   contains only values >= 0.
% - numeric_domain_positive: emitted by Python when observed numeric domain
%   contains only values > 0.
% - add_mode/sub_mode/mul_mode/div_mode/mod_mode: emitted by Python for the
%   corresponding arithmetic operator mode ids.
% Python fact detail: domain_numeric_arg(Pred,Arity,Arg) marks predicate argument Arg as numeric/domain-constrained.
#defined domain_numeric_arg/3.
% Python fact detail: zero_not_in_numeric_domain is emitted when observed numeric domain excludes 0.
#defined zero_not_in_numeric_domain/0.
% Python fact detail: numeric_domain_nonnegative is emitted when observed numeric values are all >= 0.
#defined numeric_domain_nonnegative/0.
% Python fact detail: numeric_domain_positive is emitted when observed numeric values are all > 0.
#defined numeric_domain_positive/0.
% Python fact detail: add_mode(Mode) marks arithmetic modes rendered as addition.
#defined add_mode/1.
% Python fact detail: sub_mode(Mode) marks arithmetic modes rendered as subtraction.
#defined sub_mode/1.
% Python fact detail: mul_mode(Mode) marks arithmetic modes rendered as multiplication.
#defined mul_mode/1.
% Python fact detail: div_mode(Mode) marks arithmetic modes rendered as division.
#defined div_mode/1.
% Python fact detail: mod_mode(Mode) marks arithmetic modes rendered as modulo.
#defined mod_mode/1.

% Rule: mark variables that are used in numeric domain-constrained predicate args.
% Section/Slot/Mode identify any selected literal. Pred/Arity/Arg identify a
% normal predicate argument known numeric by domain_numeric_arg. Var is the
% generated variable placed in that argument.
domain_constrained_var(Var):-
    selected(Section,Slot,Mode),
    mode(Section,Mode,Pred,Arity,_),
    domain_numeric_arg(Pred,Arity,Arg),
    var_at(Section,Slot,Arg,Var).

% Constraint: reject X-X=Result when Result must come from domain without zero.
% Slot is a subtraction literal. Value is used as both operands. Result is arg 2.
% X-X equals 0; if Result is domain constrained and 0 is absent, impossible.
:- zero_not_in_numeric_domain,
    selected(body,Slot,Mode),
    sub_mode(Mode),
    var_at(body,Slot,0,Value),
    var_at(body,Slot,1,Value),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Result).

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

% Constraint: reject nonnegative subtraction that would produce negative result.
% If Result is constrained to a nonnegative domain, Left-Right cannot satisfy
% Left < Right.
:- numeric_domain_nonnegative,
    selected(body,Slot,Mode),
    sub_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Result),
    lt_vars(Left,Right).

% Constraint: reject positive subtraction that would produce zero or negative.
% If Result must be positive, Left-Right requires Left > Right. leq_vars(Left,Right)
% contradicts that.
:- numeric_domain_positive,
    selected(body,Slot,Mode),
    sub_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Result),
    leq_vars(Left,Right).

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
