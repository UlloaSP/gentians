% Reject repeated conditions with identical template variant and bindings, but
% only when the template without the repeat is itself in the language. An exact
% attachment such as e(X,X):d(X),d(X) has no shorter declared form, so it stays.


% DEFINITION, local helper. same_condition_vars(Section, Slot, Left, Right):
% two conditions of one conditional literal are the same condition written
% twice.
%   Section, Slot  the selected conditional literal.
%   Left           index of a condition.
%   Right          index of a later condition (Left < Right) of the same
%                  variant: same predicate, polarity, term shape and
%                  placeholder types, directions and labels.
% It holds when every argument of Left holds the same variable as the matching
% argument of Right: the two #count aggregates compare the number of arguments
% with the number of arguments that agree. Used only by the constraint below.
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

% CONSTRAINT. A condition repeated with identical variables is rejected when
% the language also declares the same conditional without that repeat.
%   Section, Slot  the conditional literal.
%   Left, Right    the duplicated conditions; Right is the removable one.
%   Mode           the selected template, which has a declared variant
%                  without condition Right (conditional_shorter_mode).
%   pruned: :- p(V0) : q(V0), q(V0).     when "p : q" is also in the language
%   kept:   :- p(V0) : q(V0).
%   kept:   :- p(V0) : q(V0), q(V1).     different variables
%   kept:   :- p(V0) : q(V0), q(V0).     when the bias declares only the
%                                        two-condition attachment
:- same_condition_vars(Section, Slot, Left, Right),
    selected(Section, Slot, Mode),
    conditional_shorter_mode(Mode, Right).
