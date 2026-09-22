% Retain the existing singleton policy. Positive existential projections and
% local aggregate/conditional names are exempt. This is a search-space policy,
% not a general theorem that ASP variables must occur twice.

:- used_var(Var),
    not repeated_var(Var),
    not normal_positive_body_var(Var),
    not aggregate_local_var(_, Var),
    not conditional_local_var(_, _, Var).
