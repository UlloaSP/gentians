% Order conditions of the same template variant by their variable tuples.
% Variant identity preserves term shape and polarity.


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

:- condition_tuple_gt(Section, Slot, Left, Right).
