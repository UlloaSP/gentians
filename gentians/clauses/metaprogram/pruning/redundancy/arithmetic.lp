% Reject repeated computations and the existing removable common-factor form.
% Equal modes are tuple-sorted, so identical inputs occupy adjacent slots.
% Different result ids are syntactic bindings, not a proof of unequal values.


% DEFINITION, local helper. arithmetic_input_differs(Slot0, Slot1): two
% adjacent arithmetic literals of the same mode differ in some operand.
%   Slot0  body slot of an arithmetic literal.
%   Slot1  the next slot (Slot0 + 1), holding the same mode.
% Operands are compared side by side: left with left, right with right. Used
% only, negated, by same_arithmetic_inputs below.
arithmetic_input_differs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    arithmetic_mode(Mode),
    Slot1 = Slot0 + 1,
    arithmetic_operand(Slot0, Side, Operand),
    not arithmetic_operand(Slot1, Side, Operand).

% DEFINITION, local helper. same_arithmetic_inputs(Slot0, Slot1): two adjacent
% arithmetic literals of the same mode have the same operands, so they
% compute the same value.
%   Slot0, Slot1  adjacent body slots, as above.
% Used only by the constraint below.
same_arithmetic_inputs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    arithmetic_mode(Mode),
    Slot1 = Slot0 + 1,
    not arithmetic_input_differs(Slot0, Slot1).

% CONSTRAINT. The same computation may not be given two result variables:
% both are necessarily equal, so the clause is the one that computes it once.
%   Slot0, Slot1      adjacent arithmetic literals with identical operands.
%   Result0, Result1  their result variable ids, which differ.
%   pruned: ..., V0+V1=V2, V0+V1=V3, r(V2,V3).
%   kept:   ..., V0+V1=V2, r(V2,V2).
:- same_arithmetic_inputs(Slot0, Slot1),
    arithmetic_result(Slot0, Result0),
    arithmetic_result(Slot1, Result1),
    Result0 != Result1.

% DEFINITION, local helper. doubles_to(Mode, Var, Result): the body states
% Var + Var = Result through the addition template Mode.
%   Mode    id of the addition template.
%   Var     the variable id used as both operands.
%   Result  the result variable id.
% The slot is dropped on purpose: the constraint below only needs the
% variables, and keeping slots would ground it once per pair of slots. Used
% only by that constraint.
doubles_to(Mode, Var, Result) :-
    selected(body, Slot, Mode),
    add_mode(Mode),
    arithmetic_operand(Slot, left, Var),
    arithmetic_operand(Slot, right, Var),
    arithmetic_result(Slot, Result).

% CONSTRAINT. Two doublings may not share one result: Left+Left = Result and
% Right+Right = Result force Left = Right, which the enumerator expresses by
% writing a single variable id instead.
%   Mode    the addition template both literals use.
%   Left    the smaller of the two doubled variable ids.
%   Right   the other one; two different doubled variables are necessarily
%           two literals.
%   Result  the result variable id shared by both.
% Both doubled variables must be grounded by positive plain body atoms.
%   pruned: :- n(V0), n(V1), V0+V0=V2, V1+V1=V2.
%   kept:   :- n(V0), n(V1), V0+V0=V2, V1+V1=V3, r(V2,V3).   different results
:- doubles_to(Mode, Left, Result),
    doubles_to(Mode, Right, Result),
    Left < Right,
    normal_positive_body_var(Left),
    normal_positive_body_var(Right).
