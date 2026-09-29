% Reject repeated conditions with identical template variant and bindings, but
% only when the template without the repeat is itself in the language. An exact
% attachment such as e(X,X):d(X),d(X) has no shorter declared form, so it stays.


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

:- same_condition_vars(Section, Slot, Left, Right),
    selected(Section, Slot, Mode),
    conditional_shorter_mode(Mode, Right).
