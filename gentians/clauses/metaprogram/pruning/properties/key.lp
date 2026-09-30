% Closed-world key property.
%
% Python emits key_pred(Pred, Key) plus key_arg(Key, Arg) when the listed argument
% positions form a key for predicate Pred. Two true Pred tuples cannot share all
% key arguments while differing elsewhere. A key is a functional dependency from
% key arguments to every non-key argument, so this file exports
% functional_set_pred/3 and functional_set_arg/2 instead of duplicating
% functional dependency pruning here.
%
% This file has no constraint of its own.


% The symbolic id key(Key) cannot collide with Python's integer dependency ids.

% DEFINITION, reusable property bridge. functional_set_arg(key(Key), Arg): a
% determining position of the dependency that a key induces.
%   key(Key)  dependency id built from the key id.
%   Arg       an argument position that belongs to the key.
% Consumed by pruning/properties/functional_set.lp.
functional_set_arg(key(Key), Arg) :- key_arg(Key, Arg).

% DEFINITION, reusable property bridge. functional_set_pred(Pred, key(Key),
% Output): the key of Pred determines its argument Output.
%   Pred      signed predicate id with key Key.
%   key(Key)  the dependency id.
%   Output    each argument position of Pred outside the key.
% The arity comes from a selected positive body atom of Pred, so the facts
% exist only in models that use Pred. With key {0} of person(Id,Name,Age),
% positions 1 and 2 are determined, and functional_set.lp then prunes
% "person(V0,V1,V2), person(V0,V3,V4)".
functional_set_pred(Pred, key(Key), Output) :-
    positive_body_literal(_, _, Pred, Arity),
    key_pred(Pred, Key),
    Output = 0..Arity-1,
    not key_arg(Key, Output).
