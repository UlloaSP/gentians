% Conditional literals compiled from #modec declarations.

#defined conditional_mode/3.
#defined conditional_main_arg/2.
#defined conditional_condition/4.
#defined conditional_condition_arg/4.
#defined conditional_condition_variant/3.
#defined mode_condition_count/2.
#defined mode_condition_usage/3.
#defined condition_group_recall/2.

selected_condition_count(Count):-
    Count = #sum {
        Conditions,Section,Slot,Mode :
        selected(Section,Slot,Mode),
        mode_condition_count(Mode,Conditions)
    }.

:- body_count(Body),
    selected_condition_count(Conditions),
    max_body(Max),
    Body + Conditions > Max.

selected_condition_group_count(Group,Count):-
    condition_group_recall(Group,_),
    Count = #sum {
        Uses,Section,Slot,Mode :
        selected(Section,Slot,Mode),
        mode_condition_usage(Mode,Group,Uses)
    }.

:- selected_condition_group_count(Group,Count),
    condition_group_recall(Group,Recall),
    Count > Recall.

conditional_main_var(Section,Slot,Var):-
    selected(Section,Slot,Mode),
    conditional_main_arg(Mode,Arg),
    var_at(Section,Slot,Arg,Var).

conditional_condition_var(Section,Slot,Var):-
    selected(Section,Slot,Mode),
    conditional_condition_arg(Mode,_,_,Arg),
    var_at(Section,Slot,Arg,Var).

conditional_positive_condition_var(Section,Slot,Var):-
    selected(Section,Slot,Mode),
    conditional_condition(Mode,Condition,_,positive),
    conditional_condition_arg(Mode,Condition,_,Arg),
    var_at(Section,Slot,Arg,Var).

conditional_positive_body_main_var(body,Slot,Var):-
    selected(body,Slot,Mode),
    conditional_mode(Mode,_,_),
    not negative_mode(Mode),
    conditional_main_arg(Mode,Arg),
    var_at(body,Slot,Arg,Var).

conditional_var(Section,Slot,Var):- conditional_main_var(Section,Slot,Var).
conditional_var(Section,Slot,Var):- conditional_condition_var(Section,Slot,Var).

conditional_global_context_var(Var):-
    selected(Section,Slot,Mode),
    not conditional_mode(Mode,_,_),
    var_at(Section,Slot,_,Var).

% Body conditional variables are local unless another literal uses them.
conditional_local_var(body,Slot,Var):-
    conditional_var(body,Slot,Var),
    not conditional_global_context_var(Var).

% A head-conditional variable is local while it is absent from every ordinary
% literal. Its positive condition, rather than its head conclusion, must bind
% it. Clingo scopes the same rendered variable locally in separate conditional
% head elements.
conditional_local_var(head,Slot,Var):-
    conditional_var(head,Slot,Var),
    not conditional_global_context_var(Var).

conditional_local_at(Section,Slot,Arg):-
    selected(Section,Slot,Mode),
    conditional_local_var(Section,Slot,Var),
    var_at(Section,Slot,Arg,Var),
    conditional_mode(Mode,_,_).

:- conditional_local_var(Section,Slot,Var),
    not conditional_positive_condition_var(Section,Slot,Var),
    not conditional_positive_body_main_var(Section,Slot,Var).

conditional_global_var(Section,Slot,Var):-
    conditional_var(Section,Slot,Var),
    not conditional_local_var(Section,Slot,Var).

:- conditional_global_var(Section,Slot,Var), not safe_var(Var).

conditional_global_input_var(Var):-
    selected(Section,Slot,Mode),
    conditional_global_var(Section,Slot,Var),
    mode_arg_direction(Mode,Arg,input),
    var_at(Section,Slot,Arg,Var).

conditional_global_output_var(Var):-
    selected(Section,Slot,Mode),
    conditional_global_var(Section,Slot,Var),
    mode_arg_direction(Mode,Arg,output),
    var_at(Section,Slot,Arg,Var).

:- conditional_global_input_var(Var), not bound_var(Var).
:- conditional_global_output_var(Var), not produced_var(Var).

conditional_head_literal(Slot,Mode,Pred,Arity):-
    selected(head,Slot,Mode),
    conditional_mode(Mode,Pred,Arity).

conditional_dependency(body,Slot,Pred):-
    selected(body,Slot,Mode),
    conditional_mode(Mode,Pred,_).

conditional_dependency(Section,Slot,Pred):-
    selected(Section,Slot,Mode),
    conditional_condition(Mode,_,Pred,_).

same_condition_vars(Section,Slot,Left,Right):-
    selected(Section,Slot,Mode),
    conditional_condition_variant(Mode,Left,Variant),
    conditional_condition_variant(Mode,Right,Variant),
    Left < Right,
    Count = #count { Relative : conditional_condition_arg(Mode,Left,Relative,_) },
    Count = #count {
        Relative :
        conditional_condition_arg(Mode,Left,Relative,LeftArg),
        conditional_condition_arg(Mode,Right,Relative,RightArg),
        var_at(Section,Slot,LeftArg,Var),
        var_at(Section,Slot,RightArg,Var)
    }.

condition_tuple_gt(Section,Slot,Left,Right):-
    selected(Section,Slot,Mode),
    conditional_condition_variant(Mode,Left,Variant),
    conditional_condition_variant(Mode,Right,Variant),
    Left < Right,
    conditional_condition_arg(Mode,Left,Relative,LeftArg),
    conditional_condition_arg(Mode,Right,Relative,RightArg),
    var_at(Section,Slot,LeftArg,LeftVar),
    var_at(Section,Slot,RightArg,RightVar),
    LeftVar > RightVar,
    Relative = #count {
        Previous :
        conditional_condition_arg(Mode,Left,Previous,PreviousLeftArg),
        conditional_condition_arg(Mode,Right,Previous,PreviousRightArg),
        Previous < Relative,
        var_at(Section,Slot,PreviousLeftArg,PreviousVar),
        var_at(Section,Slot,PreviousRightArg,PreviousVar)
    }.

:- same_condition_vars(Section,Slot,Left,Right).
:- condition_tuple_gt(Section,Slot,Left,Right).
