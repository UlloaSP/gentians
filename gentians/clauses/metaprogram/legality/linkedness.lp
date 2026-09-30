% Selected literals with global variables must form one connected component.
% Local names do not connect independent scopes. Elements of a selected choice
% head are connected by that head even when they use different variables.


% DEFINITION, local helper. clause_var_at(Section, Slot, Arg, Var): a
% clause-global occurrence of Var.
%   Section, Slot  the selected literal.
%   Arg            placeholder position inside it.
%   Var            variable id written there.
% It is var_at/4 without the placeholders that are local to an aggregate, a
% conditional or a choice element (local_var_at in legality/scopes.lp). Only
% such occurrences can connect two literals. Used only in this file.
clause_var_at(Section, Slot, Arg, Var) :-
    var_at(Section, Slot, Arg, Var),
    not local_var_at(Section, Slot, Arg).

% DEFINITION, local helper. variable_literal(Section, Slot): the literal at
% that slot has at least one clause-global variable.
%   Section, Slot  the selected literal.
% A literal without any, such as a ground atom or "#count{V0 : p(V0)} > 2",
% is exempt from linkedness. Used only in this file.
variable_literal(Section, Slot) :- clause_var_at(Section, Slot, _, _).

% DEFINITION, local helper. earlier_variable_literal(Section, Slot): some
% other literal with global variables precedes this one.
%   Section, Slot  a literal with global variables that is not the first.
% "Precedes" compares (section_order, Slot): head before body, then by slot.
% Used only to define clause_root below.
earlier_variable_literal(Section, Slot) :-
    variable_literal(Section, Slot),
    variable_literal(EarlierSection, EarlierSlot),
    section_order(Section, Order),
    section_order(EarlierSection, EarlierOrder),
    (EarlierOrder, EarlierSlot) < (Order, Slot).

% DEFINITION, local helper. clause_root(Section, Slot): the first literal with
% global variables, from which connectivity is propagated.
%   Section, Slot  the first head literal that has global variables, otherwise
%                  the first body literal that has them. Exactly one exists
%                  whenever any literal has a global variable.
% Used only in this file.
clause_root(Section, Slot) :-
    variable_literal(Section, Slot),
    not earlier_variable_literal(Section, Slot).

% DEFINITION, local helper. linked_var(Var): Var is reachable from the root.
%   Var  clause-global variable id connected to the root literal through a
%        chain of literals sharing global variables.
% Used only in this file, in mutual recursion with linked_literal.
% Case 1: the variables of the root itself.
linked_var(Var) :-
    clause_root(Section, Slot),
    clause_var_at(Section, Slot, _, Var).

% DEFINITION, local helper. Same predicate. Case 2: a variable that shares a
% literal with an already linked variable.
%   Var    an already linked variable id.
%   Other  a variable id written in the same literal as Var.
linked_var(Other) :-
    linked_var(Var),
    clause_var_at(Section, Slot, _, Var),
    clause_var_at(Section, Slot, _, Other).

% DEFINITION, local helper. linked_literal(Section, Slot): the literal belongs
% to the root's connected component.
%   Section, Slot  the selected literal.
% Used by the constraint at the end of this file.
% Case 1: the root itself.
linked_literal(Section, Slot) :- clause_root(Section, Slot).

% DEFINITION, local helper. Same predicate. Case 2: a literal that mentions a
% linked variable.
linked_literal(Section, Slot) :-
    clause_var_at(Section, Slot, _, Var),
    linked_var(Var).

% DEFINITION, local helper. Same predicate. Case 3: every member of a selected
% choice, cardinality or aggregate head is linked as soon as one head literal
% is.
%   Slot  head slot of a member of the selected composite form.
% The head itself joins them: "{heads(V0);tails(V1)} :- coin(V0), coin(V1)."
% is one component although its elements share no variable.
linked_literal(head, Slot) :-
    selected_head_form(Form),
    composite_head_form(Form),
    head_form_member(Form, Slot, _),
    linked_literal(head, _).

% DEFINITION, local helper. linked_var(Var), case 3: the variables of any
% linked literal. It closes the recursion for literals linked through case 3
% above, whose variables are not otherwise reachable.
linked_var(Var) :-
    linked_literal(Section, Slot),
    clause_var_at(Section, Slot, _, Var).

% CONSTRAINT. Every literal with clause-global variables must be linked to the
% root. It is a search policy, stricter than ASP safety.
%   Section, Slot  a literal with global variables.
%   pruned: q(V0) :- d(V0), r(V1).      r(V1) shares nothing with the rest
%   pruned: :- d(V0), r(V1,V2), s(V2).  {r,s} and {d} are two components
%   kept:   q(V0) :- d(V0), r(V0).
%   kept:   q(V0) :- d(V0), r(V0,V1), s(V1).   linked through a chain
:- variable_literal(Section, Slot), not linked_literal(Section, Slot).
