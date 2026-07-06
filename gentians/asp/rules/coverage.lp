% Example coverage projection.
%
% This file is loaded by gentians.asp.clingo when evaluating whether a candidate
% hypothesis extends examples. It derives the shown atoms consumed by Python from
% lower-level coverage facts already produced by the surrounding ASP program.
%
% Shared atom shapes used here:
% - pos_exs(I): positive example id I exists.
% - neg_exs(I): negative example id I exists.
% - cpi(I): candidate covers/includes positive example I.
% - cpe(I): candidate excludes positive example I.
% - cni(I): candidate covers/includes negative example I.
% - cne(I): candidate excludes negative example I.
% - extended_p(I): shown result; positive example I is extended by candidate.
% - extended_n(I): shown result; negative example I is extended by candidate.

% Rule: mark a positive example as extended.
% I is the example id. pos_exs(I) ensures I is a positive example. cpi(I) says
% candidate includes/covers it. not cpe(I) ensures no exclusion fact cancels it.
extended_p(I):- pos_exs(I), cpi(I), not cpe(I).

% Rule: mark a negative example as extended.
% I is the example id. neg_exs(I) ensures I is a negative example. cni(I) says
% candidate includes/covers it. not cne(I) ensures no exclusion fact cancels it.
extended_n(I):- neg_exs(I), cni(I), not cne(I).

% Output directive: expose only extended positive examples to Python.
#show extended_p/1.

% Output directive: expose only extended negative examples to Python.
#show extended_n/1.
