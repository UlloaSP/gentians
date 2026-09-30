% Order conditions of the same template variant by their variable tuples.
% Variant identity preserves term shape and polarity.


% DEFINITION, local helper. condition_tuple_gt(Section, Slot, Left, Right):
% two interchangeable conditions of one conditional literal are written in
% descending order.
%   Section, Slot  the selected conditional literal.
%   Left           index of a condition.
%   Right          index of a later condition (Left < Right) of the same
%                  variant: same predicate, polarity and term shape.
% It holds when, at the first argument where the two conditions differ, the
% earlier one has the greater variable id. Relative is that argument: the
% #count requires every earlier argument (Previous < Relative) to hold equal
% variables in both conditions, which makes the comparison lexicographic.
% Used only by the constraint below.
condition_tuple_gt(Section, Slot, Left, Right) :-
    selected(Section, Slot, Mode),
    conditional_condition_variant(Mode, Left, Variant),
    conditional_condition_variant(Mode, Right, Variant),
    Left < Right,
    conditional_condition_arg(Mode, Left, Relative, LeftArg),
    conditional_condition_arg(Mode, Right, Relative, RightArg),
    var_at(Section, Slot, LeftArg, LeftVar),
    var_at(Section, Slot, RightArg, RightVar),
    LeftVar > RightVar,
    Relative = #count {
        Previous :
        conditional_condition_arg(Mode, Left, Previous, PreviousLeftArg),
        conditional_condition_arg(Mode, Right, Previous, PreviousRightArg),
        Previous < Relative,
        var_at(Section, Slot, PreviousLeftArg, PreviousVar),
        var_at(Section, Slot, PreviousRightArg, PreviousVar)
    }.

% CONSTRAINT. Conditions of the same variant inside one conditional literal
% appear in ascending order of their variable tuples; the order of conditions
% does not change the meaning.
%   Section, Slot  the conditional literal.
%   Left, Right    the two conditions found in descending order.
%   pruned: :- r(V0,V1,V2), p(V0) : q(V2), q(V1).
%   kept:   :- r(V0,V1,V2), p(V0) : q(V1), q(V2).
%   kept:   :- r(V0,V1,V2), p(V0) : q(V2), not q(V1).   different variants
:- condition_tuple_gt(Section, Slot, Left, Right).
