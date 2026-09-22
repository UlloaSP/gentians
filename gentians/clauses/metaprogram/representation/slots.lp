% Finite variable/body-slot domains and complete head-form selection.
% A selected head form activates all its members; it is never a subset choice.
% clause_body_size includes attached conditions and supplies incremental solves.
% Gapless slots and canonical ordering are enforced in symmetry/slots.lp.

#defined enumerate_by_size/0.
#defined max_vars/1.
#defined max_body/1.
#defined mode/5.
#defined head_form_member/3.

body_count(Count) :- Count = #count{Slot : selected_slot(body, Slot)}.

clause_body_size(Body+Conditions) :-
    enumerate_by_size, body_count(Body), selected_condition_count(Conditions).

var(0..Max-1) :- max_vars(Max).

body_slot(0..Max-1) :- max_body(Max), Max > 0.

section_order(head, 0).

section_order(body, 1).

head_form(Form) :- head_form_member(Form, _, _).

0 { selected_head_form(Form) : head_form(Form) } 1.

selected(head, Slot, Mode) :-
    selected_head_form(Form),
    head_form_member(Form, Slot, Mode).

0 { selected(body, Slot, Mode) : mode(body, Mode, _, _, _) } 1 :- body_slot(Slot).

selected_slot(Section, Slot) :- selected(Section, Slot, _).
