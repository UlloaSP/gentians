% Reject repeated literals of the same polarity within a section.
% Equal modes are contiguous and tuple-sorted, so adjacent checks cover repeats;
% different normal modes still require cross-slot comparisons. Opposite body
% polarities and a head/body match are handled by tautologies.lp.

% DEFINITION, local helper. same_normal_literal(Section0, Slot0, Section1,
% Slot1): two plain atoms of one section are the same literal written twice.
%   Section0, Slot0  the first occurrence.
%   Section1, Slot1  the second occurrence; always the same section as the
%                    first, and a later slot.
% "Same literal" is same predicate, same polarity, same term shape and same
% variables. Used only by the constraint below.
% Case 1: two positive atoms selected through different modes of the same
% predicate, for example one declaration with var(t,input) and another with
% var(t,output). They can sit at any two slots of the section.
same_normal_literal(Section, Slot0, Section, Slot1) :-
    positive_normal_literal(Section, Slot0, Mode0, Pred, Arity),
    positive_normal_literal(Section, Slot1, Mode1, Pred, Arity),
    Slot0 < Slot1,
    Mode0 != Mode1,
    same_term_bindings(Section, Slot0, Section, Slot1).

% DEFINITION, local helper. Same predicate. Case 2: two default-negated body
% atoms selected through different modes of the same predicate.
same_normal_literal(body, Slot0, body, Slot1) :-
    negative_body_literal(Slot0, Mode0, Pred, Arity),
    negative_body_literal(Slot1, Mode1, Pred, Arity),
    Slot0 < Slot1,
    Mode0 != Mode1,
    same_term_bindings(body, Slot0, body, Slot1).

% DEFINITION, local helper. Same predicate. Case 3: two atoms of the same
% mode, hence the same polarity. Equal modes are contiguous and sorted
% (symmetry/slots.lp), so a repeat can only sit in the next slot.
same_normal_literal(Section, Slot0, Section, Slot1) :-
    normal_literal(Section, Slot0, Mode, Pred, Arity),
    normal_literal(Section, Slot1, Mode, Pred, Arity),
    Slot1 = Slot0 + 1,
    same_term_bindings(Section, Slot0, Section, Slot1).

% CONSTRAINT. A plain atom may not be written twice in the same section.
%   Section0, Slot0, Section1, Slot1  the duplicated pair.
%   pruned: h(V0) :- p(V0,V1), p(V0,V1).
%   pruned: h(V0) :- q(V0), not p(V0), not p(V0).
%   pruned: p(V0);p(V0) :- q(V0).               a duplicate in the head
%   kept:   h(V0) :- p(V0,V1), p(V1,V0).
:- same_normal_literal(Section0, Slot0, Section1, Slot1).

% DEFINITION, local helper. same_mode_literal(body, Slot0, body, Slot1): two
% adjacent body literals of the same non-plain mode are identical.
%   body   the section; only body literals are compared.
%   Slot0  body slot of a comparison, arithmetic, aggregate, conditional or
%          boolean literal.
%   Slot1  the next slot (Slot0 + 1), holding the same mode with the same
%          variables at every placeholder.
% Used only by the constraint below.
same_mode_literal(body, Slot0, body, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    not normal_mode(Mode),
    Slot1 = Slot0 + 1,
    same_term_bindings(body, Slot0, body, Slot1).

% CONSTRAINT. A comparison, arithmetic, aggregate or conditional literal may
% not be written twice in the body.
%   Section0, Slot0, Section1, Slot1  the duplicated pair (always in the body).
%   pruned: :- p(V0,V1), V0 < V1, V0 < V1.
%   pruned: :- p(V0,V1), V0+V1=V2, V0+V1=V2, r(V2).
%   kept:   :- p(V0,V1), V0 < V1.
:- same_mode_literal(Section0, Slot0, Section1, Slot1).
