% Reject strict self comparisons and strict/non-strict reverse pairs.
% Strict/strict reverse pairs are covered by the cycle check in numeric.lp.

% CONSTRAINT. A strict comparison between a variable and itself can never
% hold, so the body is unsatisfiable.
%   Slot               body slot of a comparison outside the positive simple
%                      case already covered by pruning/policies/comparisons.lp.
%   LeftArg, RightArg  placeholders of two adjacent plain variables related by
%                      "<" or ">" (strict_comparison_args).
%   Var                the single variable id written at both.
%   pruned: :- p(V0), V0 < V0 < 3.
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

% DEFINITION, local helper. complex_numeric_builtin_selected: the selected
% body contains a builtin outside simple numeric comparisons. Its component
% may use an expression or structural fallback instead of linear normalization.
% Used only as a guard by the two constraints below; declarations that are
% not selected do not block the simple case.
complex_numeric_builtin_selected :-
    selected(body, _, Mode), complex_numeric_builtin_mode(Mode).

% DEFINITION, local helper. numeric_equality(Left, Right): a selected simple
% positive numeric equality between distinct variable ids. The symmetric view
% describes equal values; it never swaps bindings of the selected template.
% Used only by numeric_equality_path below.
numeric_equality(Left, Right) :-
    selected(body, Slot, Mode), numeric_equality_mode(Mode),
    var_at(body, Slot, 0, Left), var_at(body, Slot, 1, Right), Left != Right.
% DEFINITION, local helper. Same predicate, symmetric value equality.
numeric_equality(Right, Left) :- numeric_equality(Left, Right).

% DEFINITION, local helper. numeric_equality_path(Left, Right): selected simple
% numeric equalities connect these variables, so their values must be equal.
% Case 1: a selected equality; case 2: extend through another selected equality.
% This closure uses variable ids without products of arithmetic coefficients.
numeric_equality_path(Left, Right) :- numeric_equality(Left, Right).
numeric_equality_path(Left, Right) :-
    numeric_equality_path(Left, Middle), numeric_equality(Middle, Right).

% DEFINITION, local helper. anchored_numeric_equality(Var): Var's equality
% component has an external variable grounded by a positive plain body atom.
% This makes linear normalization applicable; components without an external
% variable retain their structural fallback.
anchored_numeric_equality(Var) :-
    numeric_equality_path(Var, Anchor), normal_positive_body_var(Anchor).

% CONSTRAINT. Equal numeric values cannot satisfy a strict comparison.
% All selected builtins must be simple numeric comparisons: otherwise the
% existing Python fallback can retain this raw form. This moves only models
% that linear normalization already discards, before decode and construction.
%   Left, Right  equality variable ids.
%   pruned: p(V0), V0=V1, V1=V2, V0<V2.
%   kept:   p(V0,V1), V0=V1, V0<=V1.
:- not complex_numeric_builtin_selected,
   anchored_numeric_equality(Left), numeric_equality_path(Left, Right),
   selected_lt(Left, Right).
% CONSTRAINT. Equal numeric values cannot satisfy a disequality.
%   Left, Right  equality variable ids.
%   pruned: p(V0), V0=V1, V1=V2, V0!=V2.
%   kept:   V0=0, V0!=0.                 no simple, anchored equality
:- not complex_numeric_builtin_selected,
   anchored_numeric_equality(Left), numeric_equality_path(Left, Right),
   selected_neq(Left, Right).

% DEFINITION, local helper. Selected builtins outside homogeneous numeric
% linear rows retain the expression/structural fallback of the whole component.
nonlinear_builtin_selected :- selected(body, _, Mode), nonlinear_builtin_mode(Mode).

% DEFINITION, local helper. A statically proved pair of proportional templates
% is selected. Project slots before comparing their complete variable bindings.
linear_conflict_slots(Equality, Comparison) :-
    numeric_linear_conflict(EqualityMode, ComparisonMode),
    selected(body, Equality, EqualityMode), selected(body, Comparison, ComparisonMode).

% DEFINITION, local helper. The paired rows disagree at some ordered binding.
% Every placeholder has one binding, and the paired rows have equal arity.
linear_conflict_bindings_differ(Equality, Comparison) :-
    linear_conflict_slots(Equality, Comparison),
    var_at(body, Equality, Arg, Var), not var_at(body, Comparison, Arg, Var).

% DEFINITION, local helper. Repeated bindings can cancel the anchored column;
% leave these cases to Python. With at most two nonzero columns and nonzero
% coefficient sum, the compiler proves that aliasing cannot erase the anchor.
linear_conflict_repeated_binding(Equality) :-
    numeric_linear_distinct_mode(Mode), selected(body, Equality, Mode),
    var_at(body, Equality, First, Var), var_at(body, Equality, Second, Var), First < Second.

% DEFINITION, local helper. Nonzero coefficients and the guarded aliasing cases
% ensure that this positive plain body anchor belongs to the actual equality row.
linear_conflict_anchored(Equality) :-
    numeric_linear_conflict(Mode, _), selected(body, Equality, Mode),
    var_at(body, Equality, _, Anchor), normal_positive_body_var(Anchor).

% CONSTRAINT. A homogeneous equality cannot coexist with its proportional
% strict comparison or disequality. This moves only normalization rejections:
%   pruned: p(V0), 2*V0=V1, 4*V0<2*V1.
%   pruned: p(V0), 2*V0=V0, 4*V0<2*V0.           nonzero collapsed row
%   kept:   p(V0), 2*V0=V1, 4*V0<2*V1, V0*V0=V1.   expression fallback
%   kept:   V0-V0=0, V0-V0!=0.                     structural fallback
% Coefficients are normalized statically in Python, never multiplied in ASP.
:- linear_conflict_slots(Equality, Comparison),
   not nonlinear_builtin_selected,
   not linear_conflict_bindings_differ(Equality, Comparison),
   not linear_conflict_repeated_binding(Equality),
   linear_conflict_anchored(Equality).
