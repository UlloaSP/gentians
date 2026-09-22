% Closed-world key property.
%
% Python emits key_pred(Pred, Key) plus key_arg(Key, Arg) when the listed argument
% positions form a key for predicate Pred. Two true Pred tuples cannot share all
% key arguments while differing elsewhere. A key is a functional dependency from
% key arguments to every non-key argument, so this file exports
% functional_set_pred/3 and functional_set_arg/2 instead of duplicating
% functional dependency pruning here.

#defined key_pred/2.
#defined key_arg/2.

% The symbolic id key(Key) cannot collide with Python's integer dependency ids.

functional_set_arg(key(Key), Arg) :- key_arg(Key, Arg).

functional_set_pred(Pred, key(Key), Output) :-
    positive_body_literal(_, _, Pred, Arity),
    key_pred(Pred, Key),
    Output = 0..Arity-1,
    not key_arg(Key, Output).
