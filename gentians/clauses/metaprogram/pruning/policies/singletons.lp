% Retain the existing singleton policy. Positive existential projections and
% local aggregate/conditional names are exempt. This is a search-space policy,
% not a general theorem that ASP variables must occur twice.

% CONSTRAINT (policy). A variable that occurs exactly once must be an
% existential projection: written in a positive plain body atom, or local to
% an aggregate or a conditional literal.
%   Var  a used variable id with a single occurrence that has none of those
%        three exemptions.
%   pruned: h(V0) :- p(V0), not q(V0,V1).    V1 occurs once, under negation
%   pruned: h(V0,V1) :- p(V0).               V1 occurs once, in the head
%   kept:   h(V0) :- p(V0,V1).               V1 occurs once in a positive atom
%   kept:   h(V0) :- p(V0), #count{V1 : q(V1,V2)} = V0.   V2 is local
:- used_var(Var),
    not repeated_var(Var),
    not normal_positive_body_var(Var),
    not aggregate_local_var(_, Var),
    not conditional_local_var(_, _, Var).
