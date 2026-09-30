% Lin and Chen, "Discovering Classes of Strongly Equivalent Logic Programs",
% IJCAI 2005, Theorem 5 (the 0-1-0 problem): a rule is strongly equivalent to
% the empty program if a positive body atom also occurs in its head or its
% default-negated body. https://cse.hkust.edu.hk/faculty/flin/papers/selp-disc-ijcai05.pdf
%
% Compare complete signed atoms: same predicate, recursive term shape and
% variable bindings. Positive/negative body overlap makes the body impossible.
% Positive body/head overlap is a tautology for normal or disjunctive heads;
% choice and cardinality heads need a separate argument and are not pruned here.

% CONSTRAINT. The body may not contain an atom together with its default
% negation: such a body is never satisfied, so the clause does nothing.
%   PosSlot          body slot of the positive atom.
%   NegSlot, NegMode body slot and mode of the negated atom, which must be a
%                    single "not"; "not not p" is excluded from this check.
%   Pred, Arity      the predicate both share.
%   pruned: h(V0) :- p(V0,V1), not p(V0,V1).
%   kept:   h(V0) :- p(V0,V1), not p(V1,V0).       different atoms
%   kept:   h(V0) :- p(V0), not not p(V0).         double negation
:- positive_body_literal(PosSlot, _, Pred, Arity),
    negative_body_literal(NegSlot, NegMode, Pred, Arity),
    not double_negative_mode(NegMode),
    same_term_bindings(body, PosSlot, body, NegSlot).

% CONSTRAINT. A plain or disjunctive head may not repeat a positive body
% atom: the clause would only derive what its body already requires.
%   HeadSlot, HeadMode  the head literal; an unconditional atom of a normal or
%                       disjunctive head (plain_disjunctive_head_mode).
%   BodySlot            body slot of the identical positive atom.
%   Pred, Arity         the predicate both share.
%   pruned: p(V0) :- p(V0), q(V0).
%   pruned: p(V0);r(V0) :- p(V0).
%   kept:   p(V0) :- p(V1), q(V0,V1).              different atoms: recursion
%   kept:   {p(V0)} :- p(V0).                      choice heads are not pruned
:- selected(head, HeadSlot, HeadMode),
    plain_disjunctive_head_mode(HeadMode),
    head_literal(HeadSlot, HeadMode, Pred, Arity),
    positive_body_literal(BodySlot, _, Pred, Arity),
    same_term_bindings(head, HeadSlot, body, BodySlot).
