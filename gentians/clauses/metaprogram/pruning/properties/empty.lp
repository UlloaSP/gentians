% Closed-world empty predicate property.
%
% Python emits empty_pred(Pred) when predicate Pred has no true ground facts in
% the closed-world evidence. Positive uses are impossible; negative uses are
% redundant because not Pred(...) is always true.


% CONSTRAINT. A positive body atom of an empty predicate makes the body
% unsatisfiable.
%   Slot  body slot of the positive atom.
%   Pred  its predicate, proved empty.
% With empty_pred(broken):
%   pruned: h(V0) :- d(V0), broken(V0).
%   kept:   h(V0) :- d(V0).
:- positive_body_literal(Slot, _, Pred, _),
    empty_pred(Pred).

% CONSTRAINT. A negated body atom of an empty predicate is always true and
% adds nothing.
%   Slot  body slot of the negated atom.
%   Pred  its predicate, proved empty.
% With empty_pred(broken):
%   pruned: h(V0) :- d(V0), not broken(V0).
%   kept:   h(V0) :- d(V0).
% Together the two constraints leave no body atom of an empty predicate.
:- negative_body_literal(Slot, _, Pred, _),
    empty_pred(Pred).
