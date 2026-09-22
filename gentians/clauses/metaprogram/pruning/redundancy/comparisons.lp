% Reject comparisons entailed by other selected comparisons.
% Replacing <= plus != requires a declared strict operator. Transitive shortcuts
% use selected edges; inferred closure must not masquerade as selected literals.

:- selected_lt(Left, Right), selected_leq(Left, Right).

:- selected_lt(Left, Right), selected_neq(Left, Right).

:- strict_comparison_available, selected_leq(Left, Right), selected_neq(Left, Right).

:- selected_lt(Left, Right), selected_lt(Left, Middle), selected_lt(Middle, Right).

:- selected_lt(Left, Right), selected_lt(Left, Middle), selected_leq(Middle, Right).

:- selected_lt(Left, Right), selected_leq(Left, Middle), selected_lt(Middle, Right).

:- selected_leq(Left, Right), selected_lt(Left, Middle), selected_lt(Middle, Right).

:- selected_leq(Left, Right), selected_lt(Left, Middle), selected_leq(Middle, Right).

:- selected_leq(Left, Right), selected_leq(Left, Middle), selected_lt(Middle, Right).

:- selected_leq(Left, Right), selected_leq(Left, Middle), selected_leq(Middle, Right).

:- selected_neq(Left, Right), selected_lt(Left, Middle), selected_lt(Middle, Right).

:- selected_neq(Left, Right), selected_lt(Left, Middle), selected_leq(Middle, Right).

:- selected_neq(Left, Right), selected_leq(Left, Middle), selected_lt(Middle, Right).
