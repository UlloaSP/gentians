% Every selected literal must belong to one variable-connected component.

#defined aggregate_head_form/1.
#defined head_form_member/3.

clause_var_at(Section,Slot,Arg,Var):-
    var_at(Section,Slot,Arg,Var),
    not conditional_local_at(Section,Slot,Arg).

variable_literal(Section,Slot):- clause_var_at(Section,Slot,_,_).

earlier_variable_literal(Section,Slot):-
    variable_literal(Section,Slot),
    variable_literal(EarlierSection,EarlierSlot),
    section_order(Section,Order),
    section_order(EarlierSection,EarlierOrder),
    (EarlierOrder,EarlierSlot) < (Order,Slot).

clause_root(Section,Slot):-
    variable_literal(Section,Slot),
    not earlier_variable_literal(Section,Slot).

linked_var(Var):-
    clause_root(Section,Slot),
    clause_var_at(Section,Slot,_,Var).

linked_var(Other):-
    linked_var(Var),
    clause_var_at(Section,Slot,_,Var),
    clause_var_at(Section,Slot,_,Other).

linked_literal(Section,Slot):- clause_root(Section,Slot).
linked_literal(Section,Slot):-
    clause_var_at(Section,Slot,_,Var),
    linked_var(Var).

% Elements of one #modeha head are structurally connected by their aggregate,
% even when their compatible atoms use different variables.
linked_literal(head,Slot):-
    selected_head_form(Form),
    aggregate_head_form(Form),
    head_form_member(Form,Slot,_),
    linked_literal(head,_).

linked_var(Var):-
    linked_literal(Section,Slot),
    clause_var_at(Section,Slot,_,Var).

:- variable_literal(Section,Slot), not linked_literal(Section,Slot).
