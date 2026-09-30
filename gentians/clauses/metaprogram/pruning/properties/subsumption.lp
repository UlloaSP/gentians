% Positive-body same-predicate subsumption.
%
% This file rejects a general positive body literal when another positive body
% literal of the same predicate is stricter and already subsumes it. It focuses
% on same-predicate literals where the stricter literal adds an equality between
% arguments.
%
% The general atom G is redundant next to the specific atom S when a
% substitution maps G onto S and moves only variables that occur nowhere
% outside G: then S already provides a witness for those variables. Position
% matters: a variable the rest of the clause uses must sit at the same
% argument in both atoms.
%   pruned: h(V0) :- p(V0,V1), p(V0,V0).       V1 -> V0 maps p(V0,V1) onto p(V0,V0)
%   kept:   h(V1) :- p(V0,V1), p(V0,V0).       V1 is needed by the head
%   kept:   :- p(V0,V0,V1), p(V1,V0,V2).       V1 sits at argument 2 of the
%                                              first atom and 0 of the second
% theta.lp already finds these substitutions between atoms of one repeatable
% mode. This file also covers atoms selected through different modes of the
% same predicate, which theta reduction never moves.
%
% In every rule GeneralSlot is the body slot of the candidate redundant atom
% (the "general" one) and SpecificSlot the body slot of the stricter atom.

% DEFINITION, local helper. subsumption_pair(GeneralSlot, SpecificSlot): two
% different positive body atoms that can be compared argument by argument.
%   GeneralSlot   body slot of a positive atom.
%   SpecificSlot  a different body slot holding a positive atom of the same
%                 predicate and the same term shape, so both atoms have the
%                 same placeholder positions and the same constants.
% Both orders of a pair are derived. Used by every rule below.
subsumption_pair(GeneralSlot, SpecificSlot) :-
    positive_body_literal(GeneralSlot, GeneralMode, Pred, Arity),
    positive_body_literal(SpecificSlot, SpecificMode, Pred, Arity),
    GeneralSlot != SpecificSlot,
    mode_shape(GeneralMode, Shape),
    mode_shape(SpecificMode, Shape).

% DEFINITION, local helper. specific_adds_equality(GeneralSlot, SpecificSlot):
% the specific atom repeats a variable where the general atom has two.
%   GeneralSlot, SpecificSlot  a subsumption pair.
% It holds when, for some pair of placeholder positions, the specific atom
% holds one variable id at both and the general atom holds two different ids,
% as p(V0,V0) against p(V0,V1). Used only by the constraint below.
specific_adds_equality(GeneralSlot, SpecificSlot) :-
    subsumption_pair(GeneralSlot, SpecificSlot),
    var_at(body, SpecificSlot, Arg0, SpecificVar),
    var_at(body, SpecificSlot, Arg1, SpecificVar),
    Arg0 < Arg1,
    var_at(body, GeneralSlot, Arg0, GeneralVar),
    not var_at(body, GeneralSlot, Arg1, GeneralVar).

% DEFINITION, local helper. general_has_extra_equality(GeneralSlot,
% SpecificSlot): the reverse situation; the general atom repeats a variable
% where the specific atom has two.
%   GeneralSlot, SpecificSlot  a subsumption pair.
% No substitution can then map the general atom onto the specific one: one
% variable would need two images, as p(V0,V0,V1) against p(V0,V1,V1). Used
% only, negated, by the constraint below.
general_has_extra_equality(GeneralSlot, SpecificSlot) :-
    subsumption_pair(GeneralSlot, SpecificSlot),
    var_at(body, GeneralSlot, Arg0, GeneralVar),
    var_at(body, GeneralSlot, Arg1, GeneralVar),
    Arg0 < Arg1,
    var_at(body, SpecificSlot, Arg0, SpecificVar),
    not var_at(body, SpecificSlot, Arg1, SpecificVar).

% Keep every variable needed outside the general literal; otherwise a join is lost.

% DEFINITION, local helper. general_var_unsupported(GeneralSlot,
% SpecificSlot): mapping the general atom onto the specific one would move a
% variable that the rest of the clause uses.
%   GeneralSlot, SpecificSlot  a subsumption pair.
% It holds when some placeholder of the general atom holds a variable that is
% used outside that atom (in the head or in another body literal, the
% specific atom included) while the specific atom holds a different variable
% at the same placeholder. Used only, negated, by the constraint below.
general_var_unsupported(GeneralSlot, SpecificSlot) :-
    subsumption_pair(GeneralSlot, SpecificSlot),
    var_at(body, GeneralSlot, Arg, Var),
    not var_at(body, SpecificSlot, Arg, Var),
    var_used_outside_body_slot(GeneralSlot, Var).

% CONSTRAINT. A positive body atom is rejected as redundant when another
% positive atom of the same predicate is stricter than it.
%   GeneralSlot   body slot of the rejected atom.
%   SpecificSlot  body slot of the stricter atom: it adds some equality, the
%                 general atom has no equality of its own that the specific
%                 one lacks, and every variable of the general atom that is
%                 used elsewhere sits at the same placeholder of the specific
%                 atom.
%   pruned and kept: see the examples in the file header.
:- subsumption_pair(GeneralSlot, SpecificSlot),
    specific_adds_equality(GeneralSlot, SpecificSlot),
    not general_has_extra_equality(GeneralSlot, SpecificSlot),
    not general_var_unsupported(GeneralSlot, SpecificSlot).
