% Reject strict self comparisons and strict/non-strict reverse pairs.
% Strict/strict reverse pairs are covered by the cycle check in numeric.lp.

% CONSTRAINT. A strict comparison between a variable and itself can never
% hold, so the body is unsatisfiable.
%   Slot               body slot of a comparison, simple or chained.
%   LeftArg, RightArg  placeholders of two adjacent plain variables related by
%                      "<" or ">" (strict_comparison_args).
%   Var                the single variable id written at both.
%   pruned: :- p(V0), V0 < V0.
%   pruned: :- p(V0), p(V1), V0 <= V1 < V1.    one strict link of a chain
%   kept:   :- p(V0), p(V1), V0 < V1.
:- selected(body, Slot, Mode),
    strict_comparison_args(Mode, LeftArg, RightArg),
    var_at(body, Slot, LeftArg, Var),
    var_at(body, Slot, RightArg, Var).

% CONSTRAINT. "Left < Right" together with "Right <= Left" can never hold.
%   Left, Right  variable ids.
%   pruned: :- p(V0,V1), V0 < V1, V1 <= V0.
%   pruned: :- p(V0,V1), V0 < V1, V0 >= V1.    ">=" is read as V1 <= V0
%   kept:   :- p(V0,V1), V0 < V1.
:- selected_lt(Left, Right), selected_leq(Right, Left).
