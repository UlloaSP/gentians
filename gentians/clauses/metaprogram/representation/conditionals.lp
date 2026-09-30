% Conditional conclusions, condition variables and predicate dependencies.
% The condition count includes attachments in both head and body. Local/global
% scope is resolved separately in legality/scopes.lp.


% DEFINITION, reusable. selected_condition_count(Count): how many conditions
% the whole clause attaches.
%   Count  sum, over every selected mode in head and body, of its
%          mode_condition_count. "p(V0):q(V0),r(V0)" contributes 2; a plain
%          atom contributes 0. Always defined; 0 when nothing is attached.
% Shared by representation/slots.lp (clause_body_size) and
% legality/clause_shape.lp (body budget): both count a condition as one body
% literal.
selected_condition_count(Count) :-
    Count = #sum {
        Conditions, Section, Slot, Mode :
        selected(Section, Slot, Mode),
        mode_condition_count(Mode, Conditions)
    }.

% DEFINITION, local helper. conditional_main_var(Section, Slot, Var): Var is
% written in the conclusion of the conditional literal at that slot.
%   Section, Slot  the selected conditional literal.
%   Var            variable id at a conclusion placeholder. In
%                  "p(V0,V1) : q(V1)" these are V0 and V1.
% Used only by conditional_var below.
conditional_main_var(Section, Slot, Var) :-
    selected(Section, Slot, Mode),
    conditional_main_arg(Mode, Arg),
    var_at(Section, Slot, Arg, Var).

% DEFINITION, local helper. conditional_condition_var(Section, Slot, Var): Var
% is written in some condition of the conditional literal at that slot.
%   Section, Slot  the selected conditional literal.
%   Var            variable id at a placeholder of any condition, whatever its
%                  polarity or kind. In "p(V0,V1) : q(V1), not r(V2)" these are
%                  V1 and V2.
% Used only by conditional_var below.
conditional_condition_var(Section, Slot, Var) :-
    selected(Section, Slot, Mode),
    conditional_condition_arg(Mode, _, _, Arg),
    var_at(Section, Slot, Arg, Var).

% DEFINITION, reusable. conditional_positive_condition_var(Section, Slot,
% Condition, Var): a positive atom condition mentions Var.
%   Section, Slot  the selected conditional literal.
%   Condition      zero-based index of the condition inside that literal.
%   Var            variable id at a placeholder of that condition, which must
%                  be an atom without default negation.
% In "p(V0) : q(V0), not r(V1)" it holds for condition 0 and V0 only. Consumed
% by legality/scopes.lp: only such a condition can bind a local variable.
conditional_positive_condition_var(Section, Slot, Condition, Var) :-
    selected(Section, Slot, Mode),
    conditional_condition(Mode, Condition, _, positive),
    conditional_condition_arg(Mode, Condition, _, Arg),
    var_at(Section, Slot, Arg, Var).

% DEFINITION, reusable. conditional_var(Section, Slot, Var): Var occurs
% anywhere in the conditional literal at that slot.
%   Section, Slot  the selected conditional literal.
%   Var            variable id of its conclusion or of any condition.
% Consumed by legality/scopes.lp, which splits these variables into local and
% global.
% Case 1: conclusion variables.
conditional_var(Section, Slot, Var) :- conditional_main_var(Section, Slot, Var).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: condition variables.
conditional_var(Section, Slot, Var) :- conditional_condition_var(Section, Slot, Var).

% DEFINITION, reusable. conditional_head_literal(Slot, Mode, Pred, Arity): a
% conditional head element concludes an atom of Pred.
%   Slot   head slot.
%   Mode   id of the selected conditional template.
%   Pred   signed predicate id of the conclusion.
%   Arity  source arity of the conclusion, not the width of the whole template.
% A default-negated conclusion ("not p(V0) : q(V0)") defines nothing and is
% excluded. Consumed by representation/literals.lp as one case of head_literal.
conditional_head_literal(Slot, Mode, Pred, Arity) :-
    selected(head, Slot, Mode),
    conditional_mode(Mode), mode_atom(Mode, Pred, Arity),
    not negative_mode(Mode).

% DEFINITION, reusable. conditional_dependency(Section, Slot, Pred): the
% literal at that slot makes the clause depend on Pred through a conditional
% construct.
%   Section  head or body: where the construct is selected.
%   Slot     its slot.
%   Pred     signed predicate id the clause reads there.
% Consumed by legality/invention.lp, which must see every predicate a clause
% reads, not only its plain body atoms.
% Case 1: the conclusion of a body conditional, as p in ":- p(V0) : q(V0)".
conditional_dependency(body, Slot, Pred) :-
    selected(body, Slot, Mode),
    conditional_mode(Mode), mode_atom(Mode, Pred, _).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: an atom condition of a conditional in either section, as q in
% "p(V0) : q(V0)". A condition is read even when it sits in the head.
conditional_dependency(Section, Slot, Pred) :-
    selected(Section, Slot, Mode),
    conditional_condition(Mode, _, Pred, _).

% DEFINITION, reusable. Same predicate and arguments.
% Case 3: an atom condition of a choice or aggregate head element, as q in
% "{p(V0) : q(V0)}".
conditional_dependency(head, Slot, Pred) :-
    selected(head, Slot, Mode),
    head_aggregate_condition_atom(Mode, _, Pred).
