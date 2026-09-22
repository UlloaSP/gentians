% Reject repeated conditions with identical template variant and bindings.

#defined conditional_condition_variant/3.

same_condition_vars(Section, Slot, Left, Right) :-
    selected(Section, Slot, Mode),
    conditional_condition_variant(Mode, Left, Variant),
    conditional_condition_variant(Mode, Right, Variant),
    Left < Right,
    Count = #count { Relative : conditional_condition_arg(Mode, Left, Relative, _) },
    Count = #count {
        Relative :
        conditional_condition_arg(Mode, Left, Relative, LeftArg),
        conditional_condition_arg(Mode, Right, Relative, RightArg),
        var_at(Section, Slot, LeftArg, Var),
        var_at(Section, Slot, RightArg, Var)
    }.

:- same_condition_vars(Section, Slot, Left, Right).
