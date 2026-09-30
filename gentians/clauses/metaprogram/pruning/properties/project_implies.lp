% Closed-world projected implication property.
%
% Python emits project_implies_pred(Pred0, Pred1, Projection) plus project_arg
% facts when Pred0 implies Pred1 after mapping source arguments to target
% arguments. Example: edge(X, Y) may imply node(X) via projection target arg 0
% from source arg 0. Target may be a learned predicate whose background lower
% bound contains the projection; only a plain head is redundant that way.
%
% The examples assume edge(X,Y) implies node(X): project_implies_pred(edge,
% node,p) with project_arg(p,0,0).


% DEFINITION, local helper. project_vars_differ(Section0, Slot0, Section1,
% Slot1, Projection): two literals are not aligned the way a projection
% requires.
%   Section0, Slot0  the literal playing the source.
%   Section1, Slot1  the literal playing the target.
%   Projection       id of a projection. Each project_arg(Projection,
%                    TargetArg, SourceArg) pairs argument SourceArg of the
%                    source with argument TargetArg of the target.
% It holds when some paired positions carry different variable ids. It is
% derived only for the pairs the next rule inspects: two plain atoms whose
% predicates the projection relates. Used only, negated, by that rule.
project_vars_differ(Section0, Slot0, Section1, Slot1, Projection) :-
    normal_literal(Section0, Slot0, _, Pred0, _),
    normal_literal(Section1, Slot1, _, Pred1, _),
    project_implies_pred(Pred0, Pred1, Projection),
    project_arg(Projection, TargetArg, SourceArg),
    var_at(Section0, Slot0, SourceArg, Var),
    arg(Section1, Slot1, TargetArg),
    not var_at(Section1, Slot1, TargetArg, Var).

% DEFINITION, local helper. project_vars_match(Section0, Slot0, Section1,
% Slot1, Projection): the target literal is exactly the projection of the
% source literal.
%   Section0, Slot0  a plain atom of the source predicate.
%   Section1, Slot1  a plain atom of the target predicate.
%   Projection       a projection from the first predicate to the second
%                    under which every paired position holds the same
%                    variable id.
% Example: edge(V0,V1) and node(V0) match; edge(V0,V1) and node(V1) do not.
% Used only by the three constraints below.
project_vars_match(Section0, Slot0, Section1, Slot1, Projection) :-
    normal_literal(Section0, Slot0, _, Pred0, _),
    normal_literal(Section1, Slot1, _, Pred1, _),
    project_implies_pred(Pred0, Pred1, Projection),
    not project_vars_differ(Section0, Slot0, Section1, Slot1, Projection).

% CONSTRAINT. A positive body atom that is the projection of another positive
% body atom is redundant.
%   Slot0         body slot of the source atom, of Pred0.
%   Slot1         a different body slot, of the target atom of Pred1.
%   Projection    the projection from Pred0 to Pred1 that aligns them.
%   pruned: h(V0) :- edge(V0,V1), node(V0).
%   kept:   h(V0) :- edge(V0,V1).               the same meaning
%   kept:   h(V0) :- edge(V0,V1), node(V1).     node(V1) is not implied
:- positive_body_literal(Slot0, _, Pred0, _),
    positive_body_literal(Slot1, _, Pred1, _),
    Slot0 != Slot1,
    project_implies_pred(Pred0, Pred1, Projection),
    project_vars_match(body, Slot0, body, Slot1, Projection).

% CONSTRAINT. A positive body atom together with the negation of its
% projection makes the body unsatisfiable.
%   Slot0  body slot of the positive source atom.
%   Slot1  a different body slot, of the negated target atom.
%   pruned: h(V0) :- edge(V0,V1), not node(V0).
%   kept:   h(V0) :- edge(V0,V1), not node(V1).
:- positive_body_literal(Slot0, _, Pred0, _),
    negative_body_literal(Slot1, _, Pred1, _),
    Slot0 != Slot1,
    project_implies_pred(Pred0, Pred1, Projection),
    project_vars_match(body, Slot0, body, Slot1, Projection).

% CONSTRAINT. A plain or disjunctive head atom that is the projection of a
% positive body atom makes the clause derive nothing new.
%   Slot0        body slot of the positive source atom.
%   Slot1, Mode  head slot and mode of the target atom; an unconditional atom
%                of a normal or disjunctive head.
% Here node is learnable and the background already derives node(X) from
% edge(X,Y), which is why the projection is proved:
%   pruned: node(V0) :- edge(V0,V1).            already in the background
%   kept:   node(V1) :- edge(V0,V1).
%   kept:   {node(V0)} :- edge(V0,V1).          choice heads are not pruned
:- positive_body_literal(Slot0, _, Pred0, _),
    head_literal(Slot1, Mode, Pred1, _),
    plain_disjunctive_head_mode(Mode),
    project_implies_pred(Pred0, Pred1, Projection),
    project_vars_match(body, Slot0, head, Slot1, Projection).
