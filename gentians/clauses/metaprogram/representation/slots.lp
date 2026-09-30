% Finite variable/body-slot domains and complete head-form selection.
% A selected head form activates all its members; it is never a subset choice.
% clause_body_size includes attached conditions and supplies incremental solves.
% Gapless slots and canonical ordering are enforced in symmetry/slots.lp.


% DEFINITION, reusable. body_count(Count): how many body slots are occupied.
%   Count  integer in 0..max_body: number of Slot with selected_slot(body, Slot).
%          Conditions attached to a conditional are not slots and are excluded.
% Shared because two consumers need the same total: clause_body_size below
% and the body budget of legality/clause_shape.lp.
body_count(Count) :- Count = #count{Slot : selected_slot(body, Slot)}.

% DEFINITION, reusable, but its consumer is Python rather than another module.
% clause_body_size(Size): total body size of the candidate clause.
%   Size  body_count plus selected_condition_count: occupied body slots plus
%         every condition attached to a selected mode, in head or body.
% Derived only when Python emits enumerate_by_size. generator.py grounds once
% and then solves one stratum per Size, passing this atom as an assumption, so
% incremental generation receives clauses grouped by size.
clause_body_size(Body+Conditions) :-
    enumerate_by_size, body_count(Body), selected_condition_count(Conditions).

% DEFINITION, reusable domain. var(Var): Var is an available variable id.
%   Var  integer in 0..Max-1, with Max from max_vars(Max); rendered as V<Var>.
%        It names a syntactic variable, never a ground value.
% Shared because representation/arguments.lp draws every var_at binding from
% this domain and symmetry/variables.lp forbids skipping ids inside it.
var(0..Max-1) :- max_vars(Max).

% DEFINITION, reusable domain. body_slot(Slot): Slot is an available body slot.
%   Slot  integer in 0..Max-1, with Max from max_body(Max). Max = 0 leaves no
%         slot, so only bodyless clauses exist.
% Shared because the body choice below opens one decision per slot, and
% representation/tuples.lp quantifies over slots that may be empty in the
% current model.
body_slot(0..Max-1) :- max_body(Max), Max > 0.

% DEFINITION, reusable fact. section_order(Section, Order): rank of a section.
%   Section  head.
%   Order    0: head literals come before every body literal.
% Shared with legality/linkedness.lp, which needs "head first" to pick the root
% literal. Clingo's own term order says body < head, the opposite.
section_order(head, 0).

% DEFINITION, reusable fact. Same predicate as above.
%   Section  body.
%   Order    1: body literals come after every head literal.
section_order(body, 1).

% DEFINITION, local helper. head_form(Form): Form is a declared head form.
%   Form  id shared by all members of one compound head declaration.
% Projects head_form_member/3 so the choice below ranges over each form once,
% not once per member.
head_form(Form) :- head_form_member(Form, _, _).

% CHOICE. Select at most one head form.
%   Form  a declared head form. None selected: the candidate is a constraint.
%   allowed: no selected_head_form atom       -> ":- edge(V0,V1)."
%   allowed: selected_head_form(3)            -> "target(V0) :- edge(V0,V1)."
%   never:   selected_head_form(3) together with selected_head_form(4)
0 { selected_head_form(Form) : head_form(Form) } 1.

% DEFINITION, reusable. selected(head, Slot, Mode): the head holds Mode at Slot.
%   head  the section; this rule only fills the head.
%   Slot  head position of the member inside its form (0, 1, ...).
%   Mode  id of the compiled language-bias template placed there.
% Every member of the selected form is derived together, which is why a form is
% never a subset choice: "red(V0);green(V0)" appears whole or not at all.
% selected/3 is the core of the reified clause: nearly every module joins on
% it, and Python's decoder reads it back to rebuild the clause.
selected(head, Slot, Mode) :-
    selected_head_form(Form),
    head_form_member(Form, Slot, Mode).

% CHOICE. Fill each body slot with at most one body mode.
%   body  the section; this rule only fills the body.
%   Slot  a body slot from body_slot/1.
%   Mode  any template declared for the body (mode_section(Mode, body)).
%   allowed: selected(body,0,M)                 one literal in slot 0
%   allowed: no selected(body,0,_)              slot 0 left empty
%   never:   selected(body,0,M) and selected(body,0,N) with M != N
% Gaps and slot permutations are removed later by symmetry/slots.lp.
0 { selected(body, Slot, Mode) : mode_section(Mode, body) } 1 :- body_slot(Slot).

% DEFINITION, reusable. selected_slot(Section, Slot): that slot is occupied.
%   Section  head or body.
%   Slot     slot position inside the section.
% Drops the Mode of selected/3. Shared because body_count above, the empty
% clause check in legality/clause_shape.lp, the headless checks in
% legality/invention.lp and pruning/task/optional_constraints.lp, and the gap
% check in symmetry/slots.lp only ask whether a slot is used, not by what.
selected_slot(Section, Slot) :- selected(Section, Slot, _).
