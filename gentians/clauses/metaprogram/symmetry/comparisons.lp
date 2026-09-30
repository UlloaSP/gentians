% Choose the ascending variable-id orientation of a symmetric comparison whose
% operands may swap: X != Y and X = Y mean Y != X and Y = X. Operands with
% different types, directions or labels are not interchangeable: with
% b(V0), a(V1) and var(a)!=var(b), V1!=V0 is the only legal orientation.
%   kept:   V0!=V1   V0=V1        pruned: V1!=V0   V1=V0

% DEFINITION, local helper. symmetric_comparison(Mode): the operator of this
% simple binary comparison means the same in both directions.
%   Mode  id of a simple comparison template.
% Used only by the constraint below.
% Case 1: disequality.
symmetric_comparison(Mode) :- comparison_operator(Mode, neq).
% DEFINITION, local helper. Same predicate. Case 2: equality.
symmetric_comparison(Mode) :- comparison_operator(Mode, eq).

% CONSTRAINT. A symmetric comparison with interchangeable operands writes them
% in ascending variable-id order.
%   Slot   body slot of the comparison.
%   Left   variable id at placeholder 0 (written on the left).
%   Right  variable id at placeholder 1 (written on the right).
%   pruned: :- p(V0), p(V1), V1 != V0.
%   kept:   :- p(V0), p(V1), V0 != V1.
% "<" and "<=" are untouched: V1 < V0 and V0 < V1 are different literals.
:- selected(body, Slot, Mode),
    symmetric_comparison(Mode),
    interchangeable_operands(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right),
    Left > Right.
