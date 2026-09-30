% Closed-world composite functional dependency property.
%
% Python emits functional_set_pred(Pred, Fd, Output) and functional_set_arg(Fd, Input)
% when a set of input arguments functionally determines one output argument.
% Positive pairs with the same determinant bindings and different output ids
% are excluded by the variable-identification policy, not because different ids
% prove different values. Negative-pair pruning requires known unequal values.


% DEFINITION, local helper. fd_inputs_differ(Slot0, Slot1, Fd): two body
% literals do not share all determining arguments of a dependency.
%   Slot0, Slot1  two body slots.
%   Fd            id of a dependency: an integer emitted by Python, or
%                 key(Key) derived by pruning/properties/key.lp.
% It holds when some input position of Fd carries different variable ids in
% the two literals. The rule does not check their predicate; the constraints
% below do. Used only, negated, by those constraints.
fd_inputs_differ(Slot0, Slot1, Fd) :-
    functional_set_arg(Fd, Input),
    var_at(body, Slot0, Input, In0),
    var_at(body, Slot1, Input, In1),
    In0 != In1.

% CONSTRAINT. Two positive atoms of a predicate that share every determining
% variable must share the determined variable. With two output ids the
% dependency would force them equal, which the enumerator expresses with one.
%   Slot0 < Slot1  body slots of the two positive atoms.
%   Pred           the predicate.
%   Fd             a dependency of Pred whose inputs are all shared.
%   Output         the argument position it determines.
%   Out0, Out1     the two different variable ids found there.
% With arguments 0 and 1 of grade(Student,Course,Mark) determining argument 2:
%   pruned: :- grade(V0,V1,V2), grade(V0,V1,V3), r(V2,V3).
%   kept:   :- grade(V0,V1,V2), grade(V0,V3,V4).    the course differs
:- positive_body_literal(Slot0, _, Pred, _),
    positive_body_literal(Slot1, _, Pred, _),
    Slot0 < Slot1,
    functional_set_pred(Pred, Fd, Output),
    not fd_inputs_differ(Slot0, Slot1, Fd),
    var_at(body, Slot0, Output, Out0),
    var_at(body, Slot1, Output, Out1),
    Out0 != Out1.

% A negative tuple with a provably different output is already implied by the positive tuple.

% CONSTRAINT. After a positive atom, negating the same determining arguments
% with a provably different determined value is always true and adds nothing.
%   PosSlot, NegSlot  body slots of the positive and the negated atom.
%   Fd, Output        a dependency of Pred whose inputs are all shared, and
%                     the position it determines.
%   Out0, Out1        the output variable ids, proved unequal in value by an
%                     explicit "!=" or "<" (known_unequal_values).
% With the same dependency of grade/3:
%   pruned: :- grade(V0,V1,V2), m(V3), V2 != V3, not grade(V0,V1,V3).
%   kept:   :- grade(V0,V1,V2), m(V3), not grade(V0,V1,V3).   V3 may equal V2
:- positive_body_literal(PosSlot, _, Pred, _),
    negative_body_literal(NegSlot, _, Pred, _),
    functional_set_pred(Pred, Fd, Output),
    not fd_inputs_differ(PosSlot, NegSlot, Fd),
    var_at(body, PosSlot, Output, Out0),
    var_at(body, NegSlot, Output, Out1),
    known_unequal_values(Out0, Out1).
