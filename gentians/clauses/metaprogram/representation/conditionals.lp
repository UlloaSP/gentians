% Conditional conclusions, condition variables and predicate dependencies.
% The condition count includes attachments in both head and body. Local/global
% scope is resolved separately in legality/scopes.lp.


selected_condition_count(Count) :-
    Count = #sum {
        Conditions, Section, Slot, Mode :
        selected(Section, Slot, Mode),
        mode_condition_count(Mode, Conditions)
    }.

conditional_main_var(Section, Slot, Var) :-
    selected(Section, Slot, Mode),
    conditional_main_arg(Mode, Arg),
    var_at(Section, Slot, Arg, Var).

conditional_condition_var(Section, Slot, Var) :-
    selected(Section, Slot, Mode),
    conditional_condition_arg(Mode, _, _, Arg),
    var_at(Section, Slot, Arg, Var).

conditional_positive_condition_var(Section, Slot, Var) :-
    selected(Section, Slot, Mode),
    conditional_condition(Mode, Condition, _, positive),
    conditional_condition_arg(Mode, Condition, _, Arg),
    var_at(Section, Slot, Arg, Var).

conditional_var(Section, Slot, Var) :- conditional_main_var(Section, Slot, Var).

conditional_var(Section, Slot, Var) :- conditional_condition_var(Section, Slot, Var).

conditional_head_literal(Slot, Mode, Pred, Arity) :-
    selected(head, Slot, Mode),
    conditional_mode(Mode), mode_atom(Mode, Pred, Arity).

conditional_dependency(body, Slot, Pred) :-
    selected(body, Slot, Mode),
    conditional_mode(Mode), mode_atom(Mode, Pred, _).

conditional_dependency(Section, Slot, Pred) :-
    selected(Section, Slot, Mode),
    conditional_condition(Mode, _, Pred, _).

conditional_dependency(head, Slot, Pred) :-
    selected(head, Slot, Mode),
    head_aggregate_condition_atom(Mode, _, Pred).
