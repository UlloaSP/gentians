% Closed-world single-input functional dependency property.
%
% Python emits functional_pred(Pred, Input, Output) when predicate Pred maps each
% value at argument Input to only one value at argument Output. Positive pairs
% with distinct output ids are excluded by the variable-identification policy:
% the dependency equates their values, not their syntactic ids. Negative-pair
% pruning instead requires a proof that the output values differ.


% CONSTRAINT. Two positive atoms of a functional predicate that share the
% input variable must share the output variable. With two output ids the
% dependency would force them equal, which the enumerator expresses with one.
%   Slot0 < Slot1  body slots of the two positive atoms.
%   Pred           the predicate.
%   Input, Output  argument positions: Input determines Output.
%   Same           the variable id both atoms hold at Input.
%   Out0, Out1     the two different variable ids they hold at Output.
% With functional_pred(mother,0,1) (each child has one mother):
%   pruned: h(V0) :- mother(V0,V1), mother(V0,V2), r(V1,V2).
%   kept:   h(V0) :- mother(V0,V1), r(V1,V1).       the same meaning
%   kept:   h(V0) :- mother(V0,V1), mother(V2,V1).  the inputs differ
:- positive_body_literal(Slot0, _, Pred, _),
    positive_body_literal(Slot1, _, Pred, _),
    Slot0 < Slot1,
    functional_pred(Pred, Input, Output),
    var_at(body, Slot0, Input, Same),
    var_at(body, Slot1, Input, Same),
    var_at(body, Slot0, Output, Out0),
    var_at(body, Slot1, Output, Out1),
    Out0 != Out1.

% A negative tuple with a provably different output is already implied by the positive tuple.

% CONSTRAINT. After a positive atom of a functional predicate, negating the
% same input with a provably different output is always true and adds
% nothing.
%   PosSlot, NegSlot  body slots of the positive and the negated atom.
%   Input, Output     argument positions: Input determines Output.
%   Same              the variable id both atoms hold at Input.
%   Out0, Out1        their output variable ids, proved unequal in value by
%                     an explicit "!=" or "<" (known_unequal_values).
% With functional_pred(mother,0,1):
%   pruned: :- mother(V0,V1), w(V2), V1 != V2, not mother(V0,V2).
%   kept:   :- mother(V0,V1), w(V2), not mother(V0,V2).   V2 may equal V1
:- positive_body_literal(PosSlot, _, Pred, _),
    negative_body_literal(NegSlot, _, Pred, _),
    functional_pred(Pred, Input, Output),
    var_at(body, PosSlot, Input, Same),
    var_at(body, NegSlot, Input, Same),
    var_at(body, PosSlot, Output, Out0),
    var_at(body, NegSlot, Output, Out1),
    known_unequal_values(Out0, Out1).
