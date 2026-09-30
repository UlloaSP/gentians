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

% CONSTRAINT. Two doublings may not share one result: Left+Left = Result and
% Right+Right = Result force Left = Right, which the enumerator expresses by
% writing a single variable id instead.
%   Slot0, Slot1  two addition literals of the same mode, Slot0 first.
%   Left          the variable id used as both operands at Slot0.
%   Right         the variable id used as both operands at Slot1; it differs
%                 from Left.
%   Result        the result variable id shared by both literals.
% Both doubled variables must be grounded by positive plain body atoms.
%   pruned: :- n(V0), n(V1), V0+V0=V2, V1+V1=V2.
%   kept:   :- n(V0), n(V1), V0+V0=V2, V1+V1=V3, r(V2,V3).   different results
:- selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    add_mode(Mode),
    Slot0 < Slot1,
    arithmetic_operand(Slot0, left, Left),
    arithmetic_operand(Slot0, right, Left),
    arithmetic_result(Slot0, Result),
    arithmetic_operand(Slot1, left, Right),
    arithmetic_operand(Slot1, right, Right),
    arithmetic_result(Slot1, Result),
    normal_positive_body_var(Left),
    normal_positive_body_var(Right),
    Left != Right.
