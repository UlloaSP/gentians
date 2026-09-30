% Classify selected literals for safety and pruning consumers.
% Normal literals exclude comparisons, arithmetic, aggregates and conditionals.
% Head classification also includes conclusions of conditional head elements.


% DEFINITION, reusable. positive_mode(Mode): Mode is not under default negation.
%   Mode  id of any compiled template that has a mode_kind and no
%         negative_mode fact. "not not p" is a negative_mode, so it is excluded.
% Shared by positive_normal_literal below and by legality/flow/seeds.lp, which
% lets only positive normal atoms bind variables.
positive_mode(Mode) :-
    mode_kind(Mode, _),
    not negative_mode(Mode).

% DEFINITION, reusable. normal_mode(Mode): Mode is a plain (possibly negated)
% atom.
%   Mode  id of a template of kind normal: not a comparison, arithmetic,
%         aggregate, conditional or boolean literal.
% Shared by normal_literal below, legality/flow/seeds.lp (binding modes) and
% pruning/redundancy/literals.lp and theta.lp (which literals may repeat/move).
normal_mode(Mode) :- mode_kind(Mode, normal).

% DEFINITION, reusable. conditional_mode(Mode): Mode is a conditional literal
% "conclusion : conditions".
%   Mode  id of a template of kind conditional.
% Shared by representation/conditionals.lp, legality/scopes.lp and
% legality/flow/declarations.lp, seeds.lp and requirements.lp, which all treat
% conditionals apart because their variables can be local.
conditional_mode(Mode) :- mode_kind(Mode, conditional).
% DEFINITION, local helper. head_aggregate_mode(Mode): Mode is one element of
% a choice, cardinality or function aggregate head.
%   Mode  id of a template of kind head_aggregate.
% Used only by the third head_literal rule below.
head_aggregate_mode(Mode) :- mode_kind(Mode, head_aggregate).

% DEFINITION, reusable. normal_literal(Section, Slot, Mode, Pred, Arity): a
% plain atom of either polarity is selected.
%   Section  head or body.
%   Slot     slot position inside the section.
%   Mode     id of the selected normal template.
%   Pred     signed predicate id of its atom; p/n and -p/n are different ids.
%   Arity    arity of that predicate as written in the source.
% Joins selected/3 with the atom signature once. Shared by the polarity views
% below and by legality/invention.lp, pruning/redundancy/literals.lp and
% several pruning/properties files that treat both polarities alike.
normal_literal(Section, Slot, Mode, Pred, Arity) :-
    selected(Section, Slot, Mode),
    normal_mode(Mode),
    mode_atom(Mode, Pred, Arity).

% DEFINITION, reusable. positive_normal_literal(Section, Slot, Mode, Pred,
% Arity): a selected plain atom without default negation.
%   Arguments as in normal_literal/5.
% Shared by positive_body_literal and head_literal below and by
% pruning/redundancy/literals.lp, which compares positive atoms in both
% sections.
positive_normal_literal(Section, Slot, Mode, Pred, Arity) :-
    normal_literal(Section, Slot, Mode, Pred, Arity),
    positive_mode(Mode).

% DEFINITION, local helper. negative_normal_literal(Section, Slot, Mode, Pred,
% Arity): a selected plain atom under "not" or "not not".
%   Arguments as in normal_literal/5.
% Used only by negative_body_literal below.
negative_normal_literal(Section, Slot, Mode, Pred, Arity) :-
    normal_literal(Section, Slot, Mode, Pred, Arity),
    negative_mode(Mode).

% DEFINITION, reusable. positive_body_literal(Slot, Mode, Pred, Arity): the
% body holds the positive plain atom Pred at Slot.
%   Slot   body slot.
%   Mode   id of the selected template.
%   Pred   signed predicate id.
%   Arity  source arity of Pred.
% The most shared view of the program: only such a literal grounds its
% variables and asserts that a tuple of Pred is true, so inference/numeric.lp,
% legality/asp_safety.lp, pruning/redundancy/tautologies.lp and almost every
% pruning/properties file start from it.
positive_body_literal(Slot, Mode, Pred, Arity) :-
    positive_normal_literal(body, Slot, Mode, Pred, Arity).

% DEFINITION, reusable. negative_body_literal(Slot, Mode, Pred, Arity): the
% body holds "not Pred(...)" or "not not Pred(...)" at Slot.
%   Arguments as in positive_body_literal/4.
% Shared by legality/asp_safety.lp (negated variables need support),
% pruning/redundancy/literals.lp and tautologies.lp, and the property files
% that detect a negation made redundant or impossible by a property.
negative_body_literal(Slot, Mode, Pred, Arity) :-
    negative_normal_literal(body, Slot, Mode, Pred, Arity).

% DEFINITION, reusable. head_literal(Slot, Mode, Pred, Arity): the clause can
% derive an atom of Pred through head Slot.
%   Slot   head slot.
%   Mode   id of the selected head template.
%   Pred   signed predicate id the head defines.
%   Arity  source arity of Pred.
% Shared by legality/invention.lp (what the clause defines),
% pruning/redundancy/tautologies.lp and pruning/properties/implies.lp and
% project_implies.lp (a head the body already guarantees).
% Case 1: a plain positive head atom, as in "p(V0) :- ..." or "p(V0);q(V0)".
head_literal(Slot, Mode, Pred, Arity) :-
    positive_normal_literal(head, Slot, Mode, Pred, Arity).

% DEFINITION, reusable. Same predicate and arguments.
% Case 2: the conclusion of a conditional head element, as in
% "p(V0) : q(V0)".
head_literal(Slot, Mode, Pred, Arity) :-
    conditional_head_literal(Slot, Mode, Pred, Arity).

% DEFINITION, reusable. Same predicate and arguments.
% Case 3: the atom of a choice, cardinality or aggregate head element that is
% not default negated, as in "{p(V0) : q(V0)}".
head_literal(Slot, Mode, Pred, Arity) :-
    selected(head, Slot, Mode), head_aggregate_mode(Mode),
    mode_atom(Mode, Pred, Arity), not negative_mode(Mode).
