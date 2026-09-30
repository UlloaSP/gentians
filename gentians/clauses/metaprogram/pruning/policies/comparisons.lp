% Exclude self comparisons and opposite non-strict edges.
% The latter force equal values, not identical variable ids; this preserves the
% existing variable-identification policy rather than asserting inconsistency.

% CONSTRAINT (policy). A simple binary comparison may not compare a variable
% with itself: it is either always true (=, <=, >=) or never true (!=, <, >).
%   Slot  body slot of a simple binary comparison, whatever its operator.
%   Var   the single variable id written at both placeholders 0 and 1.
%   pruned: :- p(V0), V0 <= V0.
%   pruned: :- p(V0), V0 != V0.
%   kept:   :- p(V0), p(V1), V0 <= V1.
:- selected(body, Slot, Mode),
    comparison_operator(Mode, _),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var).

% CONSTRAINT (policy). "Left <= Right" together with "Right <= Left" is not
% generated. The pair is satisfiable (it forces equal values), so this is not
% a contradiction: the enumerator expresses equality by writing one variable
% id instead.
%   Left, Right  variable ids.
%   pruned: h(V0) :- p(V0,V1), V0 <= V1, V1 <= V0.
%   kept:   h(V0) :- p(V0,V0).                        the same meaning
:- selected_leq(Left, Right), selected_leq(Right, Left).
