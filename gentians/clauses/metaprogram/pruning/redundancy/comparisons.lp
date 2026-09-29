% Reject comparisons entailed by other selected comparisons.
% Transitive shortcuts use selected edges; inferred closure must not masquerade
% as selected literals.
%
% X<=Y, X!=Y equals X<Y only when that X<Y is in the language: a < mode (or a
% > mode read in reverse) whose declared types admit both variables and whose
% recall is not exhausted. With <= and != on type t and < only on type u,
% h(X) :- p(X,Y), X<=Y, X!=Y has no shorter equivalent and stays.

strict_mode_for(Mode, Left, Right) :-
    comparison_operator(Mode, lt),
    selected_leq(Left, Right), selected_neq(Left, Right),
    not comparison_type_conflict(Mode, 0, Left),
    not comparison_type_conflict(Mode, 1, Right),
    not comparison_recall_full(Mode).

strict_mode_for(Mode, Left, Right) :-
    comparison_operator(Mode, gt),
    selected_leq(Left, Right), selected_neq(Left, Right),
    not comparison_type_conflict(Mode, 1, Left),
    not comparison_type_conflict(Mode, 0, Right),
    not comparison_recall_full(Mode).

comparison_type_conflict(Mode, Position, Var) :-
    comparison_operator(Mode, _),
    mode_arg_type(Mode, Position, Type),
    var_at(Section, Slot, Arg, Var),
    arg_type(Section, Slot, Arg, Other),
    Other != Type.

comparison_recall_full(Mode) :-
    comparison_operator(Mode, _),
    recall_group(Mode, Group),
    selected_count(Group, Count),
    group_recall(Group, Recall),
    Count >= Recall.

:- selected_lt(Left, Right), selected_leq(Left, Right).

:- selected_lt(Left, Right), selected_neq(Left, Right).

:- strict_mode_for(_, Left, Right).

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
