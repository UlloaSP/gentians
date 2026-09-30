% Positive-body same-predicate subsumption.
%
% This file rejects a general positive body literal when another positive body
% literal of the same predicate is stricter and already subsumes it. It focuses
% on same-predicate literals where the stricter literal adds an equality between
% arguments.
%
% In every rule GeneralSlot is the body slot of the candidate redundant atom
% (the "general" one) and SpecificSlot the body slot of the stricter atom.

% DEFINITION, local helper. specific_adds_equality(GeneralSlot, SpecificSlot):
% the specific atom repeats a variable where the general atom has two.
%   GeneralSlot   body slot of a positive atom of some predicate.
%   SpecificSlot  body slot of a positive atom of the same predicate.
% It holds when, for some pair of argument positions, the specific atom holds
% one variable id at both and the general atom holds two different ids, as
% p(V0,V0) against p(V0,V1). Used only by the constraint below.
specific_adds_equality(GeneralSlot, SpecificSlot) :-
    positive_body_literal(GeneralSlot, _, Pred, Arity),
    positive_body_literal(SpecificSlot, _, Pred, Arity),
    Arg0 = 0..Arity-1,
    Arg1 = 0..Arity-1,
    Arg0 < Arg1,
    var_at(body, SpecificSlot, Arg0, SpecificVar),
    var_at(body, SpecificSlot, Arg1, SpecificVar),
    var_at(body, GeneralSlot, Arg0, GeneralVar0),
    var_at(body, GeneralSlot, Arg1, GeneralVar1),
    GeneralVar0 != GeneralVar1.

% DEFINITION, local helper. general_has_extra_equality(GeneralSlot,
% SpecificSlot): the reverse situation; the general atom repeats a variable
% where the specific atom has two.
%   GeneralSlot, SpecificSlot  as above.
% When it holds, neither atom is more general than the other, as p(V0,V0,V1)
% against p(V0,V1,V1). Used only, negated, by the constraint below.
general_has_extra_equality(GeneralSlot, SpecificSlot) :-
    positive_body_literal(GeneralSlot, _, Pred, Arity),
    positive_body_literal(SpecificSlot, _, Pred, Arity),
    Arg0 = 0..Arity-1,
    Arg1 = 0..Arity-1,
    Arg0 < Arg1,
    var_at(body, GeneralSlot, Arg0, GeneralVar),
    var_at(body, GeneralSlot, Arg1, GeneralVar),
    var_at(body, SpecificSlot, Arg0, SpecificVar0),
    var_at(body, SpecificSlot, Arg1, SpecificVar1),
    SpecificVar0 != SpecificVar1.

% Keep every variable needed outside the general literal; otherwise a join is lost.

% DEFINITION, local helper. general_var_unsupported(GeneralSlot,
% SpecificSlot): removing the general atom would lose a variable the rest of
% the clause needs.
%   GeneralSlot   body slot of the atom that would be removed.
%   SpecificSlot  any body slot; the atom that would remain.
% It holds when a variable of the general atom is also used outside it (in
% the head or in another body literal) and does not occur in the specific
% atom. The test is occurrence anywhere in the specific atom; it does not
% require the variable to sit at the same argument position in both atoms.
% Used only, negated, by the constraint below.
general_var_unsupported(GeneralSlot, SpecificSlot) :-
    body_slot(SpecificSlot),
    var_at(body, GeneralSlot, _, Var),
    var_used_outside_body_slot(GeneralSlot, Var),
    not var_in_slot(body, SpecificSlot, Var).

% CONSTRAINT. A positive body atom is rejected as redundant when another
% positive atom of the same predicate is stricter than it.
%   GeneralSlot   body slot of the rejected atom.
%   SpecificSlot  a different body slot, of the stricter atom: not identical
%                 to the general one, with some added equality, without the
%                 general one having an equality of its own, and containing
%                 every variable of the general atom that is used elsewhere.
%   pruned: h(V0) :- p(V0,V1), p(V0,V0).     p(V0,V0) already gives a V1
%   kept:   h(V0) :- p(V0,V0).               the same meaning
%   kept:   h(V1) :- p(V0,V1), p(V0,V0).     V1 is needed by the head
:- positive_body_literal(GeneralSlot, _, Pred, Arity),
    positive_body_literal(SpecificSlot, _, Pred, Arity),
    GeneralSlot != SpecificSlot,
    not same_term_bindings(body, GeneralSlot, body, SpecificSlot),
    specific_adds_equality(GeneralSlot, SpecificSlot),
    not general_has_extra_equality(GeneralSlot, SpecificSlot),
    not general_var_unsupported(GeneralSlot, SpecificSlot).
