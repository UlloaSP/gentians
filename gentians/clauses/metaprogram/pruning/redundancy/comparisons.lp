% Reject comparisons entailed by other selected comparisons.
% Transitive shortcuts use selected edges; inferred closure must not masquerade
% as selected literals.
%
% X<=Y, X!=Y equals X<Y only when that X<Y is in the language: a < mode (or a
% > mode read in reverse) whose declared types admit both variables and whose
% recall is not exhausted. With <= and != on type t and < only on type u,
% h(X) :- p(X,Y), X<=Y, X!=Y has no shorter equivalent and stays.
%
% In the examples "..." stands for body atoms that ground the variables.

% DEFINITION, local helper. strict_mode_for(Mode, Left, Right): the pair
% "Left <= Right, Left != Right" written in the body could be replaced by one
% literal of the strict comparison template Mode.
%   Mode   id of a declared simple strict comparison.
%   Left   variable id on the smaller side of the selected "<=".
%   Right  variable id on the greater side of the selected "<=".
% Used only by the third constraint below.
% Case 1: Mode is a "<" template. Left would fill its placeholder 0 and Right
% its placeholder 1; neither may have a conflicting type, and the template
% must still have recall left.
strict_mode_for(Mode, Left, Right) :-
    comparison_operator(Mode, lt),
    selected_leq(Left, Right), selected_neq(Left, Right),
    not comparison_type_conflict(Mode, 0, Left),
    not comparison_type_conflict(Mode, 1, Right),
    not comparison_recall_full(Mode).

% DEFINITION, local helper. Same predicate. Case 2: Mode is a ">" template,
% read in reverse: "Right > Left". Right would fill placeholder 0 and Left
% placeholder 1.
strict_mode_for(Mode, Left, Right) :-
    comparison_operator(Mode, gt),
    selected_leq(Left, Right), selected_neq(Left, Right),
    not comparison_type_conflict(Mode, 1, Left),
    not comparison_type_conflict(Mode, 0, Right),
    not comparison_recall_full(Mode).

% DEFINITION, local helper. comparison_type_conflict(Mode, Position, Var):
% variable Var cannot be written at that placeholder of comparison Mode.
%   Mode      id of a simple strict comparison template.
%   Position  one of its placeholders, 0 or 1, with a declared type.
%   Var       a variable id that occurs somewhere in the clause at a
%             placeholder of a different declared type.
% Used only, negated, by strict_mode_for above.
comparison_type_conflict(Mode, Position, Var) :-
    comparison_operator(Mode, (lt; gt)),
    mode_arg_type(Mode, Position, Type),
    var_at(Section, Slot, Arg, Var),
    arg_type(Section, Slot, Arg, Other),
    Other != Type.

% DEFINITION, local helper. comparison_recall_full(Mode): no further literal
% of that comparison declaration fits in the clause.
%   Mode  id of a simple strict comparison template whose recall group
%         already has as many selected literals as its recall allows.
% Used only, negated, by strict_mode_for above.
comparison_recall_full(Mode) :-
    comparison_operator(Mode, (lt; gt)),
    recall_group(Mode, Group),
    selected_count(Group, Count),
    group_recall(Group, Recall),
    Count >= Recall.

% CONSTRAINT. "Left <= Right" is redundant next to "Left < Right".
%   Left, Right  variable ids.
%   pruned: ..., V0 < V1, V0 <= V1.
%   kept:   ..., V0 < V1.
:- selected_lt(Left, Right), selected_leq(Left, Right).

% CONSTRAINT. "Left != Right" is redundant next to "Left < Right".
%   Left, Right  variable ids.
%   pruned: ..., V0 < V1, V0 != V1.
%   kept:   ..., V0 < V1.
:- selected_lt(Left, Right), selected_neq(Left, Right).

% CONSTRAINT. "Left <= Right, Left != Right" is rejected when the language
% can say "Left < Right" directly.
%   Left, Right  the variable ids of the pair.
%   pruned: ..., V0 <= V1, V0 != V1.     when a usable "<" or ">" mode exists
%   kept:   ..., V0 < V1.
%   kept:   ..., V0 <= V1, V0 != V1.     when no strict mode admits V0 and V1
:- strict_mode_for(_, Left, Right).

% The ten constraints below remove a comparison between Left and Right that
% follows from two other selected comparisons through Middle. They join
% selected literals only, never inferred_lt. Left, Middle and Right are
% variable ids in all of them.

% CONSTRAINT. Left < Middle and Middle < Right entail Left < Right.
%   pruned: ..., V0 < V2, V0 < V1, V1 < V2.
%   kept:   ..., V0 < V1, V1 < V2.
:- selected_lt(Left, Right), selected_lt(Left, Middle), selected_lt(Middle, Right).

% CONSTRAINT. Left < Middle and Middle <= Right entail Left < Right.
%   pruned: ..., V0 < V2, V0 < V1, V1 <= V2.
%   kept:   ..., V0 < V1, V1 <= V2.
:- selected_lt(Left, Right), selected_lt(Left, Middle), selected_leq(Middle, Right).

% CONSTRAINT. Left <= Middle and Middle < Right entail Left < Right.
%   pruned: ..., V0 < V2, V0 <= V1, V1 < V2.
%   kept:   ..., V0 <= V1, V1 < V2.
:- selected_lt(Left, Right), selected_leq(Left, Middle), selected_lt(Middle, Right).

% CONSTRAINT. Left < Middle and Middle < Right entail Left <= Right.
%   pruned: ..., V0 <= V2, V0 < V1, V1 < V2.
%   kept:   ..., V0 < V1, V1 < V2.
:- selected_leq(Left, Right), selected_lt(Left, Middle), selected_lt(Middle, Right).

% CONSTRAINT. Left < Middle and Middle <= Right entail Left <= Right.
%   pruned: ..., V0 <= V2, V0 < V1, V1 <= V2.
%   kept:   ..., V0 < V1, V1 <= V2.
:- selected_leq(Left, Right), selected_lt(Left, Middle), selected_leq(Middle, Right).

% CONSTRAINT. Left <= Middle and Middle < Right entail Left <= Right.
%   pruned: ..., V0 <= V2, V0 <= V1, V1 < V2.
%   kept:   ..., V0 <= V1, V1 < V2.
:- selected_leq(Left, Right), selected_leq(Left, Middle), selected_lt(Middle, Right).

% CONSTRAINT. Left <= Middle and Middle <= Right entail Left <= Right.
%   pruned: ..., V0 <= V2, V0 <= V1, V1 <= V2.
%   kept:   ..., V0 <= V1, V1 <= V2.
:- selected_leq(Left, Right), selected_leq(Left, Middle), selected_leq(Middle, Right).

% CONSTRAINT. Left < Middle and Middle < Right entail Left != Right.
%   pruned: ..., V0 != V2, V0 < V1, V1 < V2.
%   kept:   ..., V0 < V1, V1 < V2.
:- selected_neq(Left, Right), selected_lt(Left, Middle), selected_lt(Middle, Right).

% CONSTRAINT. Left < Middle and Middle <= Right entail Left != Right.
%   pruned: ..., V0 != V2, V0 < V1, V1 <= V2.
%   kept:   ..., V0 < V1, V1 <= V2.
:- selected_neq(Left, Right), selected_lt(Left, Middle), selected_leq(Middle, Right).

% CONSTRAINT. Left <= Middle and Middle < Right entail Left != Right.
%   pruned: ..., V0 != V2, V0 <= V1, V1 < V2.
%   kept:   ..., V0 <= V1, V1 < V2.
%   kept:   ..., V0 != V2, V0 <= V1, V1 <= V2.   two "<=" do not entail "!="
:- selected_neq(Left, Right), selected_leq(Left, Middle), selected_lt(Middle, Right).
