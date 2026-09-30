% Derive sign and strict value order from selected arithmetic and the
% per-argument evidence Python proves with Clingo. positive_arg(Pred, Arg) and
% nonnegative_arg(Pred, Arg) hold when every value that argument of a closed
% predicate takes, in every model of every context, is an integer > 0 or >= 0.
% Only a positive body literal grounds its variable to such a value: a head
% atom, a negated literal or a learned predicate says nothing about it.
% inferred_lt is a transitive closure; selected_lt continues to mean an
% explicit comparison literal.


% DEFINITION, reusable. positive_value(Var): every value Var can take in the
% candidate clause is an integer > 0.
%   Var  variable id. The claim is about its ground values, not about the id.
% Shared by the rules below, pruning/contradictions/numeric.lp (impossible
% orders) and pruning/redundancy/numeric.lp (entailed comparisons).
% Case 1: a positive body atom grounds Var at an argument proved > 0. With
% positive_arg(size,1), "size(V0,V1)" in the body gives positive_value(1).
positive_value(Var) :-
    positive_body_literal(Slot, _, Pred, _),
    positive_arg(Pred, Arg),
    var_at(body, Slot, Arg, Var).

% DEFINITION, reusable. nonnegative_value(Var): every value Var can take is an
% integer >= 0.
%   Var  variable id.
% Shared by pruning/contradictions/numeric.lp and pruning/redundancy/numeric.lp.
% Case 1: a positive body atom grounds Var at an argument proved >= 0.
nonnegative_value(Var) :-
    positive_body_literal(Slot, _, Pred, _),
    nonnegative_arg(Pred, Arg),
    var_at(body, Slot, Arg, Var).

% DEFINITION, reusable. Same predicate. Case 2: > 0 entails >= 0.
nonnegative_value(Var) :- positive_value(Var).

% DEFINITION, reusable. positive_value(Result), case 2: a sum of two positive
% values is positive.
%   Slot         body slot of "Left + Right = Result" (unused beyond the join).
%   Left, Right  operand variable ids, both already positive.
%   Result       variable id of the sum, derived positive.
positive_value(Result) :-
    addition(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right).

% DEFINITION, reusable. positive_value(Value), case 3: if Value + Value is
% positive, Value is positive.
%   Slot    body slot of "Value + Value = Result".
%   Value   the variable id used as both operands, derived positive.
%   Result  variable id of the sum, already positive.
positive_value(Value) :-
    addition(Slot, Value, Value, Result),
    positive_value(Result).

% DEFINITION, reusable. positive_value(Result), case 4: a product of two
% positive values is positive.
%   Slot         body slot of "Left * Right = Result".
%   Left, Right  operand variable ids, both already positive.
%   Result       variable id of the product, derived positive.
positive_value(Result) :-
    multiplication(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right).

% DEFINITION, reusable. positive_value(Greater), case 5: a value above a
% positive value is positive.
%   Smaller  variable id already positive.
%   Greater  variable id with an explicit "Smaller < Greater" in the body.
positive_value(Greater) :- selected_lt(Smaller, Greater), positive_value(Smaller).

% DEFINITION, reusable. positive_value(Greater), case 6: the same through an
% explicit "Smaller <= Greater".
positive_value(Greater) :- selected_leq(Smaller, Greater), positive_value(Smaller).

% DEFINITION, reusable. inferred_lt(Left, Right): the clause entails that the
% value of Left is strictly below the value of Right.
%   Left   variable id of the smaller value.
%   Right  variable id of the greater value.
% Unlike selected_lt/2 it includes consequences nobody wrote as a literal.
% Consumed by pruning/contradictions/numeric.lp, which rejects a cycle.
% Case 1: every explicit strict comparison.
inferred_lt(Left, Right) :- selected_lt(Left, Right).

% DEFINITION, reusable. Same predicate. Case 2: in Left + Right = Result with
% Right > 0, Left is below Result.
%   Slot    body slot of the addition.
%   Left    left operand, the smaller value.
%   Right   right operand, already positive.
%   Result  the sum, the greater value.
inferred_lt(Left, Result) :-
    addition(Slot, Left, Right, Result),
    positive_value(Right).

% DEFINITION, reusable. Same predicate. Case 3: the mirror image; with
% Left > 0, Right is below Result.
inferred_lt(Right, Result) :-
    addition(Slot, Left, Right, Result),
    positive_value(Left).

% DEFINITION, reusable. Same predicate. Case 4: transitive closure.
%   Left, Middle, Right  variable ids with Left < Middle and Middle < Right.
inferred_lt(Left, Right) :- inferred_lt(Left, Middle), inferred_lt(Middle, Right).
