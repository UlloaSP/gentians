% Mutex predicates cannot both hold on the same terms. A positive member also
% makes negation of its partner redundant. Strong complements p/n and -p/n use
% this same rule; two default-negated members remain available.


% DEFINITION, reusable property bridge. mutex_pred(Pred0, Pred1): the two
% predicates never hold for the same tuple.
%   Pred0  signed predicate id of p/n.
%   Pred1  signed predicate id of its strong negation -p/n.
% ASP coherence forbids p(t) together with -p(t), so the pair is mutex in
% every task. mutex_pred/2 is also emitted by Python and derived by
% complement.lp and partition.lp.
mutex_pred(Pred0, Pred1) :- strong_complement_pred(Pred0, Pred1).

% DEFINITION, local helper. mutex_pair(Pred0, Pred1): the two predicates are
% mutex, available in both orders.
%   Pred0, Pred1  signed predicate ids of a mutex pair.
% Each pair is stated once; the constraints below must match whichever
% predicate they meet first. Used only by those constraints.
% Case 1: the stated order.
mutex_pair(Pred0, Pred1) :- mutex_pred(Pred0, Pred1).

% DEFINITION, local helper. Same predicate. Case 2: the reversed order.
mutex_pair(Pred1, Pred0) :- mutex_pred(Pred0, Pred1).

% CONSTRAINT. Two mutex predicates may not both be required on the same
% arguments: the body could never hold.
%   Slot0 < Slot1  body slots of the two positive atoms, with identical
%                  arguments.
%   Pred0, Pred1   a mutex pair.
% With mutex_pred(red,green):
%   pruned: h(V0) :- red(V0), green(V0).
%   kept:   h(V0) :- red(V0), green(V1), e(V0,V1).   different arguments
:- positive_body_literal(Slot0, _, Pred0, Arity),
    positive_body_literal(Slot1, _, Pred1, Arity),
    Slot0 < Slot1,
    mutex_pair(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).

% CONSTRAINT. After a positive atom, negating its mutex partner on the same
% arguments is always true and adds nothing.
%   Slot0  body slot of the positive atom, of Pred0.
%   Slot1  a different body slot, of the negated atom of Pred1.
% With mutex_pred(red,green):
%   pruned: h(V0) :- red(V0), not green(V0).
%   kept:   h(V0) :- red(V0).                       the same meaning
%   kept:   h(V0) :- d(V0), not red(V0), not green(V0).   two negations stay
:- positive_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 != Slot1,
    mutex_pair(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).
