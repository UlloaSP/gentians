% Closed-world cardinality upper-bound property.
%
% Python emits cardinality_upper_pred(Pred,Upper) when at most Upper distinct
% tuples for Pred can be true in the closed-world evidence. This file prunes
% bodies containing too many pairwise-known-distinct positive literals for Pred.
%
% Shared atom shapes used here:
% - cardinality_upper_pred(Pred,Upper): property fact. Upper is max true tuple
%   count for predicate id Pred.
% - positive_body_literal(Slot,Mode,Pred,Arity): selected positive body atom.
% - var_at(body,Slot,Arg,Var): variable at tuple argument Arg.
% - known_distinct_vars(Left,Right): comparison module proves variables differ.

% Python fact contract:
% - cardinality_upper_pred(Pred,Upper): emitted by Python when closed-world
%   evidence shows predicate id Pred can have at most Upper true tuples.
% Python fact detail: cardinality_upper_pred(Pred,Upper) gives closed-world upper bound Upper for true tuples of Pred.
#defined cardinality_upper_pred/2.

% Rule: two positive Pred literals differ at a known-distinct argument.
% Slot0 and Slot1 are ordered positive literals of same Pred and Arity. Arg is
% one predicate argument. Left and Right are variables at Arg. If they are known
% distinct, the two literal tuples are definitely different.
positive_body_tuple_known_distinct(Pred,Slot0,Slot1):-
    positive_body_literal(Slot0,_,Pred,Arity),
    positive_body_literal(Slot1,_,Pred,Arity),
    Slot0 < Slot1,
    Arg = 0..Arity-1,
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    known_distinct_vars(Left,Right).

% Rule: some pair of positive Pred literals is not proven pairwise distinct.
% Slot0 and Slot1 are ordered positive literals. If no argument is known
% distinct, the two tuples may still unify, so cardinality pruning is unsafe.
cardinality_upper_not_pairwise_distinct(Pred):-
    positive_body_literal(Slot0,_,Pred,Arity),
    positive_body_literal(Slot1,_,Pred,Arity),
    Slot0 < Slot1,
    not positive_body_tuple_known_distinct(Pred,Slot0,Slot1).

% Rule: count selected positive body literals for predicates with upper bounds.
% Pred is predicate id. Count is number of positive body slots selecting Pred.
positive_body_cardinality(Pred,Count):-
    cardinality_upper_pred(Pred,_),
    Count = #count{Slot : positive_body_literal(Slot,_,Pred,_)}.

% Constraint: reject too many pairwise-distinct positive literals.
% Count exceeds Upper for Pred. The final negation ensures every pair has a
% known-distinct argument, so these are genuinely more than Upper distinct
% tuples rather than repeated aliases.
:- cardinality_upper_pred(Pred,Upper),
    positive_body_cardinality(Pred,Count),
    Count > Upper,
    not cardinality_upper_not_pairwise_distinct(Pred).
