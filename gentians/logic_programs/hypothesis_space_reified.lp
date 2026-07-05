#defined max_depth/1.
#defined max_head/1.
#defined max_body/1.
#defined max_vars/1.
#defined mode/5.
#defined mode_arg_type/3.
#defined constraints_allowed/0.
#defined normal_mode/1.
#defined comparison_mode/1.
#defined arithmetic_mode/1.
#defined aggregate_mode/3.
#defined aggregate_condition_atom/5.
#defined symmetric_comparison_mode/1.
#defined neq_comparison_mode/1.
#defined strict_comparison_mode/1.
#defined less_than_comparison_mode/1.
#defined greater_than_comparison_mode/1.
#defined leq_comparison_mode/1.
#defined geq_comparison_mode/1.
#defined add_mode/1.
#defined sub_mode/1.
#defined mul_mode/1.
#defined div_mode/1.
#defined mod_mode/1.
#defined abs_mode/1.
#defined prune_arithmetic_identities/0.
#defined canonical_prune/0.
#defined zero_not_in_numeric_domain/0.
#defined numeric_domain_nonnegative/0.
#defined numeric_domain_positive/0.
#defined domain_numeric_arg/3.
#defined positive_mode/1.
#defined negative_mode/1.
#defined recall_group/2.
#defined group_recall/2.
#defined count_aggregate_mode/1.
#defined symmetric_pred/1.
#defined asymmetric_pred/1.
#defined antisymmetric_pred/1.
#defined acyclic_pred/1.
#defined reflexive_pred/1.
#defined strict_order_pred/1.
#defined total_order_pred/1.
#defined universal_pred/1.
#defined empty_pred/1.
#defined inverse_pred/2.
#defined implies_pred/2.
#defined equivalent_pred/2.
#defined project_implies_pred/3.
#defined project_arg/3.
#defined disjoint_arg/4.
#defined domain_disjoint_arg/4.
#defined mutex_pred/2.
#defined complement_pred/2.
#defined partition_pred/2.
#defined arg_equal_pred/3.
#defined arg_distinct_pred/3.
#defined functional_pred/3.
#defined functional_set_pred/3.
#defined functional_set_arg/2.
#defined key_pred/2.
#defined key_arg/2.
#defined cardinality_upper_pred/2.
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
    group_recall(Group,_),
    Count = #count{Section,Slot,Mode : selected(Section,Slot,Mode), recall_group(Mode,Group)}.
:- selected_count(Group,Count), group_recall(Group,Recall), Count > Recall.

arg(Section,Slot,Arg):-
    selected(Section,Slot,Mode),
    mode(Section,Mode,_,Arity,_),
    Arg = 0..Arity-1.

1 { var_at(Section,Slot,Arg,Var) : var(Var) } 1:- arg(Section,Slot,Arg).

arg_type(Section,Slot,Arg,Type):-
    selected(Section,Slot,Mode),
    mode_arg_type(Mode,Arg,Type).

normal_literal(Section,Slot,Mode,Pred,Arity):-
    selected(Section,Slot,Mode),
    normal_mode(Mode),
    mode(Section,Mode,Pred,Arity,_).

positive_normal_literal(Section,Slot,Mode,Pred,Arity):-
    normal_literal(Section,Slot,Mode,Pred,Arity),
    positive_mode(Mode).

negative_normal_literal(Section,Slot,Mode,Pred,Arity):-
    normal_literal(Section,Slot,Mode,Pred,Arity),
    negative_mode(Mode).

positive_body_literal(Slot,Mode,Pred,Arity):-
    positive_normal_literal(body,Slot,Mode,Pred,Arity).

negative_body_literal(Slot,Mode,Pred,Arity):-
    negative_normal_literal(body,Slot,Mode,Pred,Arity).

head_literal(Slot,Mode,Pred,Arity):-
    positive_normal_literal(head,Slot,Mode,Pred,Arity).

equivalent_pair(Pred0,Pred1):- equivalent_pred(Pred0,Pred1).
equivalent_pair(Pred1,Pred0):- equivalent_pred(Pred0,Pred1).

inverse_pair(Pred0,Pred1):- inverse_pred(Pred0,Pred1).
inverse_pair(Pred1,Pred0):- inverse_pred(Pred0,Pred1).

complement_pair(Pred0,Pred1):- complement_pred(Pred0,Pred1).
complement_pair(Pred1,Pred0):- complement_pred(Pred0,Pred1).

mutex_pair(Pred0,Pred1):- mutex_pred(Pred0,Pred1).
mutex_pair(Pred1,Pred0):- mutex_pred(Pred0,Pred1).
mutex_pair(Pred0,Pred1):- complement_pair(Pred0,Pred1).

join_disjoint_arg(Pred0,Arg0,Pred1,Arg1):- disjoint_arg(Pred0,Arg0,Pred1,Arg1).
join_disjoint_arg(Pred0,Arg0,Pred1,Arg1):- domain_disjoint_arg(Pred0,Arg0,Pred1,Arg1).

implies_or_equivalent(Pred0,Pred1):- implies_pred(Pred0,Pred1).
implies_or_equivalent(Pred0,Pred1):- equivalent_pair(Pred0,Pred1).

irreflexive_pred(Pred):- asymmetric_pred(Pred).
irreflexive_pred(Pred):- strict_order_pred(Pred).
irreflexive_pred(Pred):- acyclic_pred(Pred).

antisymmetric_like_pred(Pred):- antisymmetric_pred(Pred).
antisymmetric_like_pred(Pred):- strict_order_pred(Pred).
antisymmetric_like_pred(Pred):- total_order_pred(Pred).
antisymmetric_like_pred(Pred):- acyclic_pred(Pred).

transitive_like_pred(Pred):- transitive_pred(Pred).
transitive_like_pred(Pred):- strict_order_pred(Pred).
transitive_like_pred(Pred):- total_order_pred(Pred).

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
    positive_body_literal(Slot,Mode,_,_),
    var_at(body,Slot,_,Var).

safe_var(Var):- normal_positive_body_var(Var).

head_var(Var):- var_at(head,_,_,Var).
negated_var(Var):-
    negative_body_literal(Slot,Mode,_,_),
    var_at(body,Slot,_,Var).

comparison_var(Var):-
    selected(body,Slot,Mode),
    comparison_mode(Mode),
    var_at(body,Slot,_,Var).

arithmetic_operand_var(Var):-
    selected(body,Slot,Mode),
    arithmetic_mode(Mode),
    Arg = 0..1,
    var_at(body,Slot,Arg,Var).

arithmetic_result_safe(Slot):-
    selected(body,Slot,Mode),
    arithmetic_mode(Mode),
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
    arithmetic_mode(Mode),
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

aggregate_condition_arg(Slot,Pred,LocalArg,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    aggregate_condition_atom(Mode,_,Pred,Offset,Arity),
    LocalArg = 0..Arity-1,
    Arg = TupleArity + Offset + LocalArg,
    var_at(body,Slot,Arg,Var).

safe_var(Var):- aggregate_result_var(_,Var).

:- aggregate_result_var(Slot,Var),
    not var_used_outside_body_slot(Slot,Var).

:- head_var(Var), not safe_var(Var).
:- negated_var(Var), not safe_var(Var).
:- comparison_var(Var), not safe_var(Var).
:- arithmetic_operand_var(Var), not safe_var(Var).

:- selected(body,Slot,Mode),
    comparison_mode(Mode),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).

:- selected(Section,Slot,Mode),
    normal_literal(Section,Slot,Mode,Pred,_),
    arg_equal_pred(Pred,Arg0,Arg1),
    var_at(Section,Slot,Arg0,Var0),
    var_at(Section,Slot,Arg1,Var1),
    Var0 != Var1.

:- selected(Section,Slot,Mode),
    normal_literal(Section,Slot,Mode,Pred,_),
    arg_distinct_pred(Pred,Arg0,Arg1),
    var_at(Section,Slot,Arg0,Var),
    var_at(Section,Slot,Arg1,Var).

:- selected(Section,Slot,Mode),
    normal_literal(Section,Slot,Mode,Pred,2),
    symmetric_pred(Pred),
    var_at(Section,Slot,0,Left),
    var_at(Section,Slot,1,Right),
    Left > Right.

:- selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,_,Pred,Offset,_),
    arg_equal_pred(Pred,LocalArg0,LocalArg1),
    aggregate_condition_arg(Slot,Pred,LocalArg0,Var0),
    aggregate_condition_arg(Slot,Pred,LocalArg1,Var1),
    Var0 != Var1.

:- selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,_,Pred,Offset,_),
    arg_distinct_pred(Pred,LocalArg0,LocalArg1),
    aggregate_condition_arg(Slot,Pred,LocalArg0,Var),
    aggregate_condition_arg(Slot,Pred,LocalArg1,Var).

:- selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,_,Pred,Offset,2),
    symmetric_pred(Pred),
    aggregate_condition_arg(Slot,Pred,0,Left),
    aggregate_condition_arg(Slot,Pred,1,Right),
    Left > Right.

:- canonical_prune,
    selected(body,Slot,Mode),
    symmetric_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    Left > Right.

:- selected(body,Slot,Mode),
    arithmetic_mode(Mode),
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

arithmetic_input_differs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    arithmetic_mode(Mode),
    Arg = 0..1,
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    Left != Right.

same_arithmetic_inputs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    arithmetic_mode(Mode),
    Slot0 < Slot1,
    not arithmetic_input_differs(Slot0,Slot1).

:- same_arithmetic_inputs(Slot0,Slot1),
    var_at(body,Slot0,2,Result0),
    var_at(body,Slot1,2,Result1),
    Result0 != Result1.

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

lt_vars(Left,Right):-
    selected(body,Slot,Mode),
    less_than_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

lt_vars(Right,Left):-
    selected(body,Slot,Mode),
    greater_than_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

leq_vars(Left,Right):-
    selected(body,Slot,Mode),
    leq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

leq_vars(Right,Left):-
    selected(body,Slot,Mode),
    geq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

:- lt_vars(Left,Right), lt_vars(Right,Left).
:- lt_vars(Left,Right), leq_vars(Right,Left).
:- lt_vars(Left,Right), leq_vars(Left,Right).
:- leq_vars(Left,Right), leq_vars(Right,Left).
:- lt_vars(Left,Right), neq_vars(Left,Right).

:- numeric_domain_nonnegative,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Left),
    domain_constrained_var(Result),
    lt_vars(Result,Left).

:- numeric_domain_nonnegative,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Right),
    domain_constrained_var(Result),
    lt_vars(Result,Right).

:- numeric_domain_positive,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Left),
    domain_constrained_var(Right),
    domain_constrained_var(Result),
    leq_vars(Result,Left).

:- numeric_domain_positive,
    selected(body,Slot,Mode),
    add_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Left),
    domain_constrained_var(Right),
    domain_constrained_var(Result),
    leq_vars(Result,Right).

:- numeric_domain_nonnegative,
    selected(body,Slot,Mode),
    sub_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Result),
    lt_vars(Left,Right).

:- numeric_domain_positive,
    selected(body,Slot,Mode),
    sub_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Result),
    leq_vars(Left,Right).

:- numeric_domain_positive,
    selected(body,Slot,Mode),
    mod_mode(Mode),
    var_at(body,Slot,1,Divisor),
    var_at(body,Slot,2,Result),
    domain_constrained_var(Divisor),
    domain_constrained_var(Result),
    leq_vars(Divisor,Result).

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

project_vars_differ(Section0,Slot0,Section1,Slot1,Projection):-
    project_arg(Projection,TargetArg,SourceArg),
    var_at(Section0,Slot0,SourceArg,SourceVar),
    var_at(Section1,Slot1,TargetArg,TargetVar),
    SourceVar != TargetVar.

project_vars_match(Section0,Slot0,Section1,Slot1,Projection):-
    normal_literal(Section0,Slot0,_,Pred0,_),
    normal_literal(Section1,Slot1,_,Pred1,_),
    project_implies_pred(Pred0,Pred1,Projection),
    not project_vars_differ(Section0,Slot0,Section1,Slot1,Projection).

var_in_slot(Section,Slot,Var):-
    var_at(Section,Slot,_,Var).

positive_body_var_outside_slot(Slot,Var):-
    body_slot(Slot),
    positive_body_literal(OtherSlot,_,_,_),
    OtherSlot != Slot,
    var_at(body,OtherSlot,_,Var).

:- normal_literal(Section,Slot0,_,Pred0,Arity),
    normal_literal(Section,Slot1,_,Pred1,Arity),
    Slot0 < Slot1,
    equivalent_pred(Pred0,Pred1),
    same_vars(Section,Slot0,Section,Slot1).

:- positive_body_literal(Slot0,_,Pred0,_),
    positive_body_literal(Slot1,_,Pred1,_),
    Slot0 < Slot1,
    join_disjoint_arg(Pred0,Arg0,Pred1,Arg1),
    var_at(body,Slot0,Arg0,Var),
    var_at(body,Slot1,Arg1,Var).

universal_literal_missing_guard(Slot):-
    positive_body_literal(Slot,_,Pred,_),
    universal_pred(Pred),
    var_at(body,Slot,_,Var),
    not positive_body_var_outside_slot(Slot,Var).

:- positive_body_literal(Slot,_,Pred,_),
    universal_pred(Pred),
    not universal_literal_missing_guard(Slot).

:- negative_body_literal(Slot,_,Pred,_),
    universal_pred(Pred).

:- positive_body_literal(Slot,_,Pred,_),
    empty_pred(Pred).

:- negative_body_literal(Slot,_,Pred,_),
    empty_pred(Pred).

partition_neg_has(Part,Anchor,Pred):-
    negative_body_literal(Anchor,_,AnchorPred,Arity),
    negative_body_literal(Slot,_,Pred,Arity),
    partition_pred(Part,AnchorPred),
    partition_pred(Part,Pred),
    same_vars(body,Anchor,body,Slot).

partition_neg_missing(Part,Anchor):-
    negative_body_literal(Anchor,_,AnchorPred,_),
    partition_pred(Part,AnchorPred),
    partition_pred(Part,Pred),
    not partition_neg_has(Part,Anchor,Pred).

:- negative_body_literal(Anchor,_,AnchorPred,_),
    partition_pred(Part,AnchorPred),
    not partition_neg_missing(Part,Anchor).

:- positive_body_literal(PosSlot,_,PosPred,Arity),
    negative_body_literal(NegSlot,_,NegPred,Arity),
    partition_pred(Part,PosPred),
    partition_pred(Part,NegPred),
    same_vars(body,PosSlot,body,NegSlot).

key_inputs_differ(Slot0,Slot1,Key):-
    key_arg(Key,Arg),
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    Left != Right.

slot_vars_differ(body,Slot0,body,Slot1):-
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    Left != Right.

:- positive_body_literal(Slot0,_,Pred,_),
    positive_body_literal(Slot1,_,Pred,_),
    Slot0 < Slot1,
    key_pred(Pred,Key),
    not key_inputs_differ(Slot0,Slot1,Key),
    slot_vars_differ(body,Slot0,body,Slot1).

:- positive_body_literal(Slot,_,Pred,2),
    reflexive_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var),
    positive_body_var_outside_slot(Slot,Var).

:- positive_body_literal(Slot,_,Pred,2),
    total_order_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var),
    positive_body_var_outside_slot(Slot,Var).

:- negative_body_literal(Slot,_,Pred,2),
    reflexive_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).

:- negative_body_literal(Slot,_,Pred,2),
    total_order_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).

:- negative_body_literal(Slot0,_,Pred,2),
    negative_body_literal(Slot1,_,Pred,2),
    Slot0 < Slot1,
    total_order_pred(Pred),
    var_at(body,Slot0,0,Left),
    var_at(body,Slot0,1,Right),
    Left != Right,
    var_at(body,Slot1,0,Right),
    var_at(body,Slot1,1,Left).

specific_adds_equality(GeneralSlot,SpecificSlot):-
    positive_body_literal(GeneralSlot,_,Pred,Arity),
    positive_body_literal(SpecificSlot,_,Pred,Arity),
    Arg0 = 0..Arity-1,
    Arg1 = 0..Arity-1,
    Arg0 < Arg1,
    var_at(body,SpecificSlot,Arg0,SpecificVar),
    var_at(body,SpecificSlot,Arg1,SpecificVar),
    var_at(body,GeneralSlot,Arg0,GeneralVar0),
    var_at(body,GeneralSlot,Arg1,GeneralVar1),
    GeneralVar0 != GeneralVar1.

general_has_extra_equality(GeneralSlot,SpecificSlot):-
    positive_body_literal(GeneralSlot,_,Pred,Arity),
    positive_body_literal(SpecificSlot,_,Pred,Arity),
    Arg0 = 0..Arity-1,
    Arg1 = 0..Arity-1,
    Arg0 < Arg1,
    var_at(body,GeneralSlot,Arg0,GeneralVar),
    var_at(body,GeneralSlot,Arg1,GeneralVar),
    var_at(body,SpecificSlot,Arg0,SpecificVar0),
    var_at(body,SpecificSlot,Arg1,SpecificVar1),
    SpecificVar0 != SpecificVar1.

general_var_unsupported(GeneralSlot,SpecificSlot):-
    body_slot(SpecificSlot),
    var_at(body,GeneralSlot,_,Var),
    var_used_outside_body_slot(GeneralSlot,Var),
    not var_in_slot(body,SpecificSlot,Var).

:- positive_body_literal(GeneralSlot,_,Pred,Arity),
    positive_body_literal(SpecificSlot,_,Pred,Arity),
    GeneralSlot != SpecificSlot,
    not same_vars(body,GeneralSlot,body,SpecificSlot),
    specific_adds_equality(GeneralSlot,SpecificSlot),
    not general_has_extra_equality(GeneralSlot,SpecificSlot),
    not general_var_unsupported(GeneralSlot,SpecificSlot).

:- positive_body_literal(Slot0,_,Pred0,2),
    positive_body_literal(Slot1,_,Pred1,2),
    Slot0 < Slot1,
    inverse_pair(Pred0,Pred1),
    reversed_binary_vars(body,Slot0,body,Slot1).

:- positive_body_literal(Slot0,_,Pred0,2),
    negative_body_literal(Slot1,_,Pred1,2),
    inverse_pair(Pred0,Pred1),
    reversed_binary_vars(body,Slot0,body,Slot1).

:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    Slot0 < Slot1,
    irreflexive_pred(Pred),
    reversed_binary_vars(body,Slot0,body,Slot1).

:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    Slot0 < Slot1,
    antisymmetric_like_pred(Pred),
    var_at(body,Slot0,0,Left),
    var_at(body,Slot0,1,Right),
    Left != Right,
    var_at(body,Slot1,0,Right),
    var_at(body,Slot1,1,Left).

:- positive_body_literal(Slot,_,Pred,2),
    irreflexive_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).

:- positive_body_literal(Slot0,_,Pred0,Arity),
    positive_body_literal(Slot1,_,Pred1,Arity),
    Slot0 != Slot1,
    implies_or_equivalent(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).

:- positive_body_literal(Slot0,_,Pred0,Arity),
    head_literal(Slot1,_,Pred1,Arity),
    implies_or_equivalent(Pred0,Pred1),
    same_vars(body,Slot0,head,Slot1).

:- positive_body_literal(Slot0,_,Pred0,Arity),
    negative_body_literal(Slot1,_,Pred1,Arity),
    Slot0 != Slot1,
    implies_or_equivalent(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).

:- positive_body_literal(Slot0,_,Pred0,_),
    positive_body_literal(Slot1,_,Pred1,_),
    Slot0 != Slot1,
    project_implies_pred(Pred0,Pred1,Projection),
    project_vars_match(body,Slot0,body,Slot1,Projection).

:- positive_body_literal(Slot0,_,Pred0,_),
    negative_body_literal(Slot1,_,Pred1,_),
    Slot0 != Slot1,
    project_implies_pred(Pred0,Pred1,Projection),
    project_vars_match(body,Slot0,body,Slot1,Projection).

:- positive_body_literal(Slot0,_,Pred0,_),
    head_literal(Slot1,_,Pred1,_),
    project_implies_pred(Pred0,Pred1,Projection),
    project_vars_match(body,Slot0,head,Slot1,Projection).

:- positive_body_literal(Slot0,_,Pred0,Arity),
    positive_body_literal(Slot1,_,Pred1,Arity),
    Slot0 < Slot1,
    mutex_pair(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).

:- positive_body_literal(Slot0,_,Pred0,Arity),
    negative_body_literal(Slot1,_,Pred1,Arity),
    Slot0 != Slot1,
    mutex_pair(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).

:- negative_body_literal(Slot0,_,Pred0,Arity),
    negative_body_literal(Slot1,_,Pred1,Arity),
    Slot0 < Slot1,
    complement_pair(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).

:- positive_body_literal(Slot0,_,Pred,_),
    positive_body_literal(Slot1,_,Pred,_),
    Slot0 < Slot1,
    functional_pred(Pred,Input,Output),
    var_at(body,Slot0,Input,Same),
    var_at(body,Slot1,Input,Same),
    var_at(body,Slot0,Output,Out0),
    var_at(body,Slot1,Output,Out1),
    Out0 != Out1.

neq_vars(Left,Right):-
    selected(body,Slot,Mode),
    neq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

neq_vars(Right,Left):- neq_vars(Left,Right).

strict_comparison_vars(Left,Right):-
    selected(body,Slot,Mode),
    strict_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

known_distinct_vars(Left,Right):- neq_vars(Left,Right).
known_distinct_vars(Left,Right):- strict_comparison_vars(Left,Right).
known_distinct_vars(Right,Left):- known_distinct_vars(Left,Right).

positive_body_tuple_known_distinct(Pred,Slot0,Slot1):-
    positive_body_literal(Slot0,_,Pred,Arity),
    positive_body_literal(Slot1,_,Pred,Arity),
    Slot0 < Slot1,
    Arg = 0..Arity-1,
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    known_distinct_vars(Left,Right).

cardinality_upper_not_pairwise_distinct(Pred):-
    positive_body_literal(Slot0,_,Pred,Arity),
    positive_body_literal(Slot1,_,Pred,Arity),
    Slot0 < Slot1,
    not positive_body_tuple_known_distinct(Pred,Slot0,Slot1).

positive_body_cardinality(Pred,Count):-
    cardinality_upper_pred(Pred,_),
    Count = #count{Slot : positive_body_literal(Slot,_,Pred,_)}.

:- cardinality_upper_pred(Pred,Upper),
    positive_body_cardinality(Pred,Count),
    Count > Upper,
    not cardinality_upper_not_pairwise_distinct(Pred).

key_output_arg(Pred,Key,Arg):-
    positive_body_literal(_,_,Pred,Arity),
    key_pred(Pred,Key),
    Arg = 0..Arity-1,
    not key_arg(Key,Arg).

:- positive_body_literal(PosSlot,_,Pred,_),
    negative_body_literal(NegSlot,_,Pred,_),
    functional_pred(Pred,Input,Output),
    var_at(body,PosSlot,Input,Same),
    var_at(body,NegSlot,Input,Same),
    var_at(body,PosSlot,Output,Out0),
    var_at(body,NegSlot,Output,Out1),
    known_distinct_vars(Out0,Out1).

:- positive_body_literal(PosSlot,_,Pred,_),
    negative_body_literal(NegSlot,_,Pred,_),
    key_pred(Pred,Key),
    not key_inputs_differ(PosSlot,NegSlot,Key),
    key_output_arg(Pred,Key,Output),
    var_at(body,PosSlot,Output,Out0),
    var_at(body,NegSlot,Output,Out1),
    known_distinct_vars(Out0,Out1).

fd_inputs_differ(Slot0,Slot1,Fd):-
    functional_set_arg(Fd,Input),
    var_at(body,Slot0,Input,In0),
    var_at(body,Slot1,Input,In1),
    In0 != In1.

:- positive_body_literal(Slot0,_,Pred,_),
    positive_body_literal(Slot1,_,Pred,_),
    Slot0 < Slot1,
    functional_set_pred(Pred,Fd,Output),
    not fd_inputs_differ(Slot0,Slot1,Fd),
    var_at(body,Slot0,Output,Out0),
    var_at(body,Slot1,Output,Out1),
    Out0 != Out1.

:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    positive_body_literal(Slot2,_,Pred,2),
    Slot0 < Slot1,
    Slot1 < Slot2,
    transitive_like_pred(Pred),
    var_at(body,Slot0,0,X),
    var_at(body,Slot0,1,Y),
    var_at(body,Slot1,0,Y),
    var_at(body,Slot1,1,Z),
    var_at(body,Slot2,0,X),
    var_at(body,Slot2,1,Z).

:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    negative_body_literal(Slot2,_,Pred,2),
    transitive_like_pred(Pred),
    var_at(body,Slot0,0,X),
    var_at(body,Slot0,1,Y),
    var_at(body,Slot1,0,Y),
    var_at(body,Slot1,1,Z),
    var_at(body,Slot2,0,X),
    var_at(body,Slot2,1,Z).

:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    positive_body_literal(Slot2,_,Pred,2),
    Slot0 < Slot1,
    Slot1 < Slot2,
    acyclic_pred(Pred),
    var_at(body,Slot0,0,X),
    var_at(body,Slot0,1,Y),
    var_at(body,Slot1,0,Y),
    var_at(body,Slot1,1,Z),
    var_at(body,Slot2,0,Z),
    var_at(body,Slot2,1,X).

:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    negative_body_literal(Slot2,_,Pred,2),
    acyclic_pred(Pred),
    var_at(body,Slot0,0,X),
    var_at(body,Slot0,1,Y),
    var_at(body,Slot1,0,Y),
    var_at(body,Slot1,1,Z),
    var_at(body,Slot2,0,Z),
    var_at(body,Slot2,1,X).

:- selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    A0 = 0..TupleArity-1,
    A1 = 0..TupleArity-1,
    A0 < A1,
    var_at(body,Slot,A0,Var),
    var_at(body,Slot,A1,Var).

:- canonical_prune,
    selected(body,Slot,Mode),
    count_aggregate_mode(Mode),
    aggregate_mode(Mode,TupleArity,_),
    A0 = 0..TupleArity-1,
    A1 = 0..TupleArity-1,
    A0 < A1,
    var_at(body,Slot,A0,Left),
    var_at(body,Slot,A1,Right),
    Left > Right.

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

aggregate_input_differs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    aggregate_mode(Mode,_,_),
    aggregate_internal_arg(Slot0,Arg),
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    Left != Right.

same_aggregate_inputs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    aggregate_mode(Mode,_,_),
    Slot0 < Slot1,
    not aggregate_input_differs(Slot0,Slot1).

:- same_aggregate_inputs(Slot0,Slot1),
    aggregate_result_var(Slot0,Result0),
    aggregate_result_var(Slot1,Result1),
    Result0 != Result1.

same_normal_literal(Section0,Slot0,Section1,Slot1):-
    normal_literal(Section0,Slot0,_,Pred,Arity),
    normal_literal(Section1,Slot1,_,Pred,Arity),
    section_order(Section0,Order0),
    section_order(Section1,Order1),
    (Order0,Slot0) < (Order1,Slot1),
    Arity = #count{Arg : var_at(Section0,Slot0,Arg,Var), var_at(Section1,Slot1,Arg,Var)}.

:- same_normal_literal(Section0,Slot0,Section1,Slot1).

same_mode_literal(Section0,Slot0,Section1,Slot1):-
    selected(Section0,Slot0,Mode),
    selected(Section1,Slot1,Mode),
    not normal_mode(Mode),
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
