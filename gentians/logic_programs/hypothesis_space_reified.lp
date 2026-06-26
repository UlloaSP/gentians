#defined max_head/1.
#defined max_body/1.
#defined max_vars/1.
#defined mode/5.
#defined normal_mode/1.
#defined comparison_mode/2.
#defined arithmetic_mode/2.
#defined aggregate_mode/3.
#defined aggregate_atom/3.
#defined positive_mode/1.
#defined negative_mode/1.
#defined recall/2.

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

:- not selected_slot(body,_).
:- not selected_slot(head,_), #count{Slot : selected_slot(body,Slot)} < 2.

arg(Section,Slot,Arg):-
    selected(Section,Slot,Mode),
    mode(Section,Mode,_,Arity,_),
    Arg = 0..Arity-1.

1 { var_at(Section,Slot,Arg,Var) : var(Var) } 1:- arg(Section,Slot,Arg).

used_var(Var):- var_at(_,_,_,Var).

repeated_var(Var):-
    var_at(S0,L0,A0,Var),
    var_at(S1,L1,A1,Var),
    (S0,L0,A0) < (S1,L1,A1).

:- used_var(Var), not repeated_var(Var).
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

:- head_var(Var), not safe_var(Var).
:- negated_var(Var), not safe_var(Var).
:- comparison_var(Var), not safe_var(Var).
:- arithmetic_operand_var(Var), not safe_var(Var).

:- selected(body,Slot,Mode),
    comparison_mode(Mode,_),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).

:- selected(body,Slot,Mode),
    arithmetic_mode(Mode,_),
    var_at(body,Slot,Operand,Var),
    Operand = 0..1,
    var_at(body,Slot,2,Var).

:- selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    A0 = 0..TupleArity-1,
    A1 = 0..TupleArity-1,
    A0 < A1,
    var_at(body,Slot,A0,Var),
    var_at(body,Slot,A1,Var).

:- aggregate_tuple_var(Slot,Var), not aggregate_condition_var(Slot,Var).
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

#show selected/3.
#show var_at/4.
