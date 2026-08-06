% Every selected literal must belong to one variable-connected component.

variable_literal(Section,Slot):- var_at(Section,Slot,_,_).

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
    var_at(Section,Slot,_,Var).

linked_var(Other):-
    linked_var(Var),
    var_at(Section,Slot,_,Var),
    var_at(Section,Slot,_,Other).

linked_literal(Section,Slot):- clause_root(Section,Slot).
linked_literal(Section,Slot):-
    var_at(Section,Slot,_,Var),
    linked_var(Var).

:- variable_literal(Section,Slot), not linked_literal(Section,Slot).
