% Choose dense variable ids ordered by their first occurrence.
% These comparisons order syntactic ids, not their object-level values.

% CONSTRAINT. Variable ids are used without gaps, starting at 0.
%   Var1  a used variable id.
%   Var0  a smaller id of the domain that is not used.
%   pruned: :- edge(V0,V2).      V1 is skipped
%   kept:   :- edge(V0,V1).
:- used_var(Var1), var(Var0), Var0 < Var1, not used_var(Var0).

% DEFINITION, local helper. first_var_pos(Var, Section, Slot, Arg): where Var
% first occurs.
%   Var      a used variable id.
%   Section  section of its first occurrence.
%   Slot     slot of its first occurrence.
%   Arg      placeholder position of its first occurrence.
% "First" is the minimum of (Section, Slot, Arg) in Clingo's term order, in
% which body < head: a body occurrence precedes every head occurrence. Used
% only by the constraint below.
first_var_pos(Var, Section, Slot, Arg) :-
    used_var(Var),
    (Section, Slot, Arg) = #min{(S, L, A) : var_at(S, L, A, Var)}.

% CONSTRAINT. Ids grow in the order of first occurrence: a smaller id never
% first occurs after a greater one. Renaming variables does not change a
% clause, so one naming per clause is kept.
%   Var0, Var1            two used ids with Var0 < Var1.
%   (S0,L0,A0), (S1,L1,A1)  their first positions.
%   pruned: :- edge(V1,V0).                   V1 occurs before V0
%   kept:   :- edge(V0,V1).
%   kept:   target(V1,V0) :- edge(V0,V1).     the body is read first, so the
%                                             head may list ids in any order
:- first_var_pos(Var0, S0, L0, A0),
    first_var_pos(Var1, S1, L1, A1),
    Var0 < Var1,
    (S0, L0, A0) > (S1, L1, A1).
