#defined max_depth/1.
#defined max_head/1.
#defined max_body/1.
#defined max_vars/1.
#defined mode/5.
#defined mode_arg_type/3.
#defined constraints_allowed/0.
#defined normal_mode/1.
#defined comparison_mode/2.
#defined arithmetic_mode/2.
#defined aggregate_mode/3.
#defined irreflexive_mode/1.
#defined symmetric_comparison_mode/1.
#defined add_mode/1.
#defined sub_mode/1.
#defined mul_mode/1.
#defined abs_mode/1.
#defined prune_redundant_comparisons/0.
#defined prune_arithmetic_identities/0.
#defined canonical_prune/0.
#defined zero_not_in_numeric_domain/0.
#defined domain_numeric_arg/3.
#defined positive_mode/1.
#defined negative_mode/1.
#defined recall/2.
#defined recall_group/2.
#defined symmetric_pred/1.
#defined inverse_pred/2.
#defined implies_pred/2.
#defined mutex_pred/2.
#defined arg_equal_pred/3.
#defined arg_distinct_pred/3.
#defined functional_pred/3.
#defined transitive_pred/1.

var(0..Max-1):- max_vars(Max).
head_slot(0..Max-1):- max_head(Max), Max > 0.
body_slot(0..Max-1):- max_body(Max), Max > 0.
section_order(head,0).
section_order(body,1).

0 { selected(head,Slot,Mode) : mode(head,Mode,_,_,_) } 1:- head_slot(Slot).
0 { selected(body,Slot,Mode) : mode(body,Mode,_,_,_) } 1:- body_slot(Slot).

selected_slot(Section,Slot):- selected(Section,Slot,_).

:- selected_slot(Section,Slot), Slot > 0, not selected_slot(Section,Slot-1).
:- selected(Section,Slot0,Mode0), selected(Section,Slot1,Mode1), Slot0 < Slot1, Mode0 > Mode1.

same_mode_tuple_gt(Section,Slot0,Slot1):-
    canonical_prune,
    selected(Section,Slot0,Mode),
    selected(Section,Slot1,Mode),
    Slot0 < Slot1,
    mode(Section,Mode,_,Arity,_),
    Arg = 0..Arity-1,
    var_at(Section,Slot0,Arg,Left),
    var_at(Section,Slot1,Arg,Right),
    Left > Right,
    Arg = #count{
        Prev : Prev = 0..Arg-1,
        var_at(Section,Slot0,Prev,Same),
        var_at(Section,Slot1,Prev,Same)
    }.

:- same_mode_tuple_gt(Section,Slot0,Slot1).

:- not selected_slot(body,_).
:- not selected_slot(head,_), not constraints_allowed.
:- not selected_slot(head,_), #count{Slot : selected_slot(body,Slot)} < 2.
head_count(Count):- Count = #count{Slot : selected_slot(head,Slot)}.
body_count(Count):- Count = #count{Slot : selected_slot(body,Slot)}.
:- max_depth(Max), head_count(Head), body_count(Body), Head + Body > Max.

selected_count(Group,Count):-
    recall_group(_,Group),
    Count = #count{Section,Slot,Mode : selected(Section,Slot,Mode), recall_group(Mode,Group)}.
:- selected_count(Group,Count), recall_group(Mode,Group), recall(Mode,Recall), Count > Recall.

arg(Section,Slot,Arg):-
    selected(Section,Slot,Mode),
    mode(Section,Mode,_,Arity,_),
    Arg = 0..Arity-1.

1 { var_at(Section,Slot,Arg,Var) : var(Var) } 1:- arg(Section,Slot,Arg).

arg_type(Section,Slot,Arg,Type):-
    selected(Section,Slot,Mode),
    mode_arg_type(Mode,Arg,Type).

:- var_at(Section0,Slot0,Arg0,Var),
    var_at(Section1,Slot1,Arg1,Var),
    arg_type(Section0,Slot0,Arg0,Type0),
    arg_type(Section1,Slot1,Arg1,Type1),
    Type0 != any,
    Type1 != any,
    Type0 != Type1.

used_var(Var):- var_at(_,_,_,Var).

repeated_var(Var):-
    var_at(S0,L0,A0,Var),
    var_at(S1,L1,A1,Var),
    (S0,L0,A0) < (S1,L1,A1).

aggregate_local_var(Slot,Var):-
    aggregate_condition_var(Slot,Var),
    not aggregate_tuple_var(Slot,Var),
    not aggregate_result_var(Slot,Var).

:- used_var(Var), not repeated_var(Var), not aggregate_local_var(_,Var).
:- used_var(Var1), var(Var0), Var0 < Var1, not used_var(Var0).

first_var_pos(Var,Section,Slot,Arg):-
    used_var(Var),
    (Section,Slot,Arg) = #min{(S,L,A) : var_at(S,L,A,Var)}.

:- first_var_pos(Var0,S0,L0,A0),
    first_var_pos(Var1,S1,L1,A1),
    Var0 < Var1,
    (S0,L0,A0) > (S1,L1,A1).

normal_positive_body_var(Var):-
    selected(body,Slot,Mode),
    normal_mode(Mode),
    positive_mode(Mode),
    var_at(body,Slot,_,Var).

safe_var(Var):- normal_positive_body_var(Var).

head_var(Var):- var_at(head,_,_,Var).
negated_var(Var):-
    selected(body,Slot,Mode),
    negative_mode(Mode),
    var_at(body,Slot,_,Var).

comparison_var(Var):-
    selected(body,Slot,Mode),
    comparison_mode(Mode,_),
    var_at(body,Slot,_,Var).

arithmetic_operand_var(Var):-
    selected(body,Slot,Mode),
    arithmetic_mode(Mode,_),
    Arg = 0..1,
    var_at(body,Slot,Arg,Var).

arithmetic_result_safe(Slot):-
    selected(body,Slot,Mode),
    arithmetic_mode(Mode,_),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    safe_var(Left),
    safe_var(Right).

safe_var(Var):-
    arithmetic_result_safe(Slot),
    var_at(body,Slot,2,Var).

var_used_outside_body_slot(Slot,Var):- body_slot(Slot), var_at(head,_,_,Var).
var_used_outside_body_slot(Slot,Var):-
    body_slot(Slot),
    var_at(body,OtherSlot,_,Var),
    OtherSlot != Slot.

:- selected(body,Slot,Mode),
    arithmetic_mode(Mode,_),
    var_at(body,Slot,2,Var),
    not var_used_outside_body_slot(Slot,Var).

aggregate_tuple_var(Slot,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    Arg = 0..TupleArity-1,
    var_at(body,Slot,Arg,Var).

aggregate_condition_var(Slot,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    mode(body,Mode,_,Arity,_),
    Arg = TupleArity..Arity-2,
    var_at(body,Slot,Arg,Var).

aggregate_result_var(Slot,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,_,_),
    mode(body,Mode,_,Arity,_),
    Result = Arity-1,
    var_at(body,Slot,Result,Var).

aggregate_internal_arg(Slot,Arg):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,_,_),
    mode(body,Mode,_,Arity,_),
    Arg = 0..Arity-2.

safe_var(Var):- aggregate_result_var(_,Var).

:- aggregate_result_var(Slot,Var),
    not var_used_outside_body_slot(Slot,Var).

:- head_var(Var), not safe_var(Var).
:- negated_var(Var), not safe_var(Var).
:- comparison_var(Var), not safe_var(Var).
:- arithmetic_operand_var(Var), not safe_var(Var).

:- selected(body,Slot,Mode),
    comparison_mode(Mode,_),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).

:- selected(Section,Slot,Mode),
    irreflexive_mode(Mode),
    var_at(Section,Slot,Arg0,Var),
    var_at(Section,Slot,Arg1,Var),
    Arg0 < Arg1.

:- selected(Section,Slot,Mode),
    normal_mode(Mode),
    mode(Section,Mode,Pred,_,_),
    arg_equal_pred(Pred,Arg0,Arg1),
    var_at(Section,Slot,Arg0,Var0),
    var_at(Section,Slot,Arg1,Var1),
    Var0 != Var1.

:- selected(Section,Slot,Mode),
    normal_mode(Mode),
    mode(Section,Mode,Pred,_,_),
    arg_distinct_pred(Pred,Arg0,Arg1),
    var_at(Section,Slot,Arg0,Var),
    var_at(Section,Slot,Arg1,Var).

:- selected(Section,Slot,Mode),
    normal_mode(Mode),
    mode(Section,Mode,Pred,2,_),
    symmetric_pred(Pred),
    var_at(Section,Slot,0,Left),
    var_at(Section,Slot,1,Right),
    Left > Right.

:- prune_redundant_comparisons,
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    symmetric_comparison_mode(Mode),
    Slot0 < Slot1,
    var_at(body,Slot0,0,Left),
    var_at(body,Slot0,1,Right),
    var_at(body,Slot1,0,Right),
    var_at(body,Slot1,1,Left).

:- selected(body,Slot,Mode),
    arithmetic_mode(Mode,_),
    var_at(body,Slot,Operand,Var),
    Operand = 0..1,
    var_at(body,Slot,2,Var).

:- canonical_prune,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

:- canonical_prune,
    selected(body,Slot,Mode),
    mul_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

:- canonical_prune,
    selected(body,Slot,Mode),
    abs_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

domain_constrained_var(Var):-
    selected(Section,Slot,Mode),
    mode(Section,Mode,Pred,Arity,_),
    domain_numeric_arg(Pred,Arity,Arg),
    var_at(Section,Slot,Arg,Var).

:- zero_not_in_numeric_domain,
    selected(body,Slot,Mode),
    sub_mode(Mode),
    var_at(body,Slot,0,Value),
    var_at(body,Slot,1,Value),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Result).

:- prune_arithmetic_identities,
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    add_mode(Mode),
    Slot0 < Slot1,
    var_at(body,Slot0,0,Left),
    var_at(body,Slot0,1,Right),
    var_at(body,Slot0,2,Result),
    var_at(body,Slot1,0,Right),
    var_at(body,Slot1,1,Left),
    var_at(body,Slot1,2,Result).

:- prune_arithmetic_identities,
    selected(body,AddSlot,AddMode),
    selected(body,SubSlot,SubMode),
    add_mode(AddMode),
    sub_mode(SubMode),
    var_at(body,AddSlot,0,Left),
    var_at(body,AddSlot,1,Right),
    var_at(body,AddSlot,2,Result),
    var_at(body,SubSlot,0,Result),
    var_at(body,SubSlot,1,Left),
    var_at(body,SubSlot,2,Right).

:- prune_arithmetic_identities,
    selected(body,AddSlot,AddMode),
    selected(body,SubSlot,SubMode),
    add_mode(AddMode),
    sub_mode(SubMode),
    var_at(body,AddSlot,0,Left),
    var_at(body,AddSlot,1,Right),
    var_at(body,AddSlot,2,Result),
    var_at(body,SubSlot,0,Result),
    var_at(body,SubSlot,1,Right),
    var_at(body,SubSlot,2,Left).

same_vars(Section0,Slot0,Section1,Slot1):-
    selected(Section0,Slot0,Mode0),
    selected(Section1,Slot1,Mode1),
    mode(Section0,Mode0,_,Arity,_),
    mode(Section1,Mode1,_,Arity,_),
    Arity = #count{Arg : var_at(Section0,Slot0,Arg,Var), var_at(Section1,Slot1,Arg,Var)}.

reversed_binary_vars(Section0,Slot0,Section1,Slot1):-
    var_at(Section0,Slot0,0,Left),
    var_at(Section0,Slot0,1,Right),
    var_at(Section1,Slot1,0,Right),
    var_at(Section1,Slot1,1,Left).

:- selected(body,Slot0,Mode0),
    selected(body,Slot1,Mode1),
    Slot0 < Slot1,
    normal_mode(Mode0),
    normal_mode(Mode1),
    positive_mode(Mode0),
    positive_mode(Mode1),
    mode(body,Mode0,Pred0,2,_),
    mode(body,Mode1,Pred1,2,_),
    inverse_pred(Pred0,Pred1),
    reversed_binary_vars(body,Slot0,body,Slot1).

:- selected(body,Slot0,Mode0),
    selected(body,Slot1,Mode1),
    Slot0 != Slot1,
    normal_mode(Mode0),
    normal_mode(Mode1),
    positive_mode(Mode0),
    positive_mode(Mode1),
    mode(body,Mode0,Pred0,Arity,_),
    mode(body,Mode1,Pred1,Arity,_),
    implies_pred(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).

:- selected(body,Slot0,Mode0),
    selected(body,Slot1,Mode1),
    Slot0 != Slot1,
    normal_mode(Mode0),
    normal_mode(Mode1),
    positive_mode(Mode0),
    negative_mode(Mode1),
    mode(body,Mode0,Pred0,Arity,_),
    mode(body,Mode1,Pred1,Arity,_),
    implies_pred(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).

:- selected(body,Slot0,Mode0),
    selected(body,Slot1,Mode1),
    Slot0 < Slot1,
    normal_mode(Mode0),
    normal_mode(Mode1),
    positive_mode(Mode0),
    positive_mode(Mode1),
    mode(body,Mode0,Pred0,Arity,_),
    mode(body,Mode1,Pred1,Arity,_),
    mutex_pred(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).

:- selected(body,Slot0,Mode0),
    selected(body,Slot1,Mode1),
    Slot0 < Slot1,
    normal_mode(Mode0),
    normal_mode(Mode1),
    positive_mode(Mode0),
    positive_mode(Mode1),
    mode(body,Mode0,Pred,_,_),
    mode(body,Mode1,Pred,_,_),
    functional_pred(Pred,Input,Output),
    var_at(body,Slot0,Input,Same),
    var_at(body,Slot1,Input,Same),
    var_at(body,Slot0,Output,Out0),
    var_at(body,Slot1,Output,Out1),
    Out0 != Out1.

:- selected(body,Slot0,Mode0),
    selected(body,Slot1,Mode1),
    selected(body,Slot2,Mode2),
    Slot0 < Slot1,
    Slot1 < Slot2,
    normal_mode(Mode0),
    normal_mode(Mode1),
    normal_mode(Mode2),
    positive_mode(Mode0),
    positive_mode(Mode1),
    positive_mode(Mode2),
    mode(body,Mode0,Pred,2,_),
    mode(body,Mode1,Pred,2,_),
    mode(body,Mode2,Pred,2,_),
    transitive_pred(Pred),
    var_at(body,Slot0,0,X),
    var_at(body,Slot0,1,Y),
    var_at(body,Slot1,0,Y),
    var_at(body,Slot1,1,Z),
    var_at(body,Slot2,0,X),
    var_at(body,Slot2,1,Z).

:- selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    A0 = 0..TupleArity-1,
    A1 = 0..TupleArity-1,
    A0 < A1,
    var_at(body,Slot,A0,Var),
    var_at(body,Slot,A1,Var).

:- selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    mode(body,Mode,_,Arity,_),
    A0 = TupleArity..Arity-2,
    A1 = TupleArity..Arity-2,
    A0 < A1,
    var_at(body,Slot,A0,Var),
    var_at(body,Slot,A1,Var).

:- aggregate_tuple_var(Slot,Var), not aggregate_condition_var(Slot,Var).
:- aggregate_condition_var(Slot,Var),
    not aggregate_tuple_var(Slot,Var),
    var_used_outside_body_slot(Slot,Var),
    not normal_positive_body_var(Var).
:- aggregate_condition_var(_,Var), aggregate_result_var(_,Var), not normal_positive_body_var(Var).
:- aggregate_tuple_var(Slot,Var),
    var_at(head,_,_,Var).
:- aggregate_tuple_var(Slot,Var),
    var_at(body,OtherSlot,_,Var),
    OtherSlot != Slot.
:- aggregate_tuple_var(Slot,Var),
    var_at(body,Slot,Arg,Var),
    not aggregate_internal_arg(Slot,Arg).

same_normal_literal(Section0,Slot0,Section1,Slot1):-
    selected(Section0,Slot0,Mode0),
    selected(Section1,Slot1,Mode1),
    normal_mode(Mode0),
    normal_mode(Mode1),
    section_order(Section0,Order0),
    section_order(Section1,Order1),
    (Order0,Slot0) < (Order1,Slot1),
    mode(Section0,Mode0,Pred,Arity,_),
    mode(Section1,Mode1,Pred,Arity,_),
    Arity = #count{Arg : var_at(Section0,Slot0,Arg,Var), var_at(Section1,Slot1,Arg,Var)}.

:- same_normal_literal(Section0,Slot0,Section1,Slot1).

same_mode_literal(Section0,Slot0,Section1,Slot1):-
    selected(Section0,Slot0,Mode),
    selected(Section1,Slot1,Mode),
    section_order(Section0,Order0),
    section_order(Section1,Order1),
    (Order0,Slot0) < (Order1,Slot1),
    mode(Section0,Mode,_,Arity,_),
    Arity = #count{Arg : var_at(Section0,Slot0,Arg,Var), var_at(Section1,Slot1,Arg,Var)}.

:- same_mode_literal(Section0,Slot0,Section1,Slot1).

code_prefix(Section,Slot,Mode,0,0):-
    selected(Section,Slot,Mode).

code_prefix(Section,Slot,Mode,NextArg,NextCode):-
    code_prefix(Section,Slot,Mode,Arg,Code),
    mode(Section,Mode,_,Arity,_),
    Arg < Arity,
    NextArg = Arg + 1,
    max_vars(Base),
    var_at(Section,Slot,Arg,Var),
    NextCode = (Code * Base) + Var.

lit(Section,Slot,Mode,Code):-
    selected(Section,Slot,Mode),
    mode(Section,Mode,_,Arity,_),
    code_prefix(Section,Slot,Mode,Arity,Code).

#show lit/4.
