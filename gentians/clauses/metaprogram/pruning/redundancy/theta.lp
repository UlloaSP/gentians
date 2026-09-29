% Theta reduction: reject a clause C when a substitution theta maps every
% literal of C onto a literal of C other than some selected literal O. Then
% C is equivalent to its proper subclause C theta, which is also enumerated.
%
% Movable literals are normal body atoms (either polarity) of a mode with
% recall > 1. Every other literal, and every literal whose mode occurs once,
% maps to itself and fixes its variables: comparisons, arithmetic, aggregates,
% conditionals and every head stay untouched instead of blocking the check.
% Head literals never move because dropping one can leave the language:
%   kept:   p(X);p(Y) :- d(X), d(Y).   Y -> X gives p(X) :- d(X), equivalent but
%                                     not generated under #minhl(2)
%
%   pruned: q(X) :- p(X,Y), p(X,Z).            Z -> Y maps p(X,Z) onto p(X,Y)
%   pruned: :- r(A,B), r(A,C), s(A,D), B != D.  C -> B; B and D stay fixed
%   pruned: q(X) :- p(X,Y), p(X,Z), o(Y), o(Z). Z -> Y folds p and o together
%   kept:   q(X) :- p(X,Y), p(Y,Z).            no substitution folds either atom
%   kept:   :- r(A,B), r(A,C), B != C.          C occurs in the comparison
%
% Python chooses one of two exact encodings of "some substitution exists":
% enumerated offsets while they stay few, saturation otherwise.

theta_movable(Mode, body) :-
    mode_section(Mode, body), normal_mode(Mode), mode_recall(Mode, Recall), Recall > 1.

theta_section(Section) :- theta_sigma_section(Section).
theta_section(Section) :- theta_saturated_section(Section).

% Only a clause repeating a movable mode can be theta-redundant.
theta_repeated(Section, Slot) :-
    theta_section(Section),
    selected(Section, Slot, Mode), theta_movable(Mode, Section),
    selected(Section, Other, Mode), Slot != Other.
theta_active :- theta_repeated(_, _).

theta_fixed(Var) :-
    theta_active, var_at(Section, Slot, _, Var), not theta_repeated(Section, Slot).

% Enumerated offsets (a normal program). Equal modes occupy contiguous slots
% (symmetry/slots.lp), so a repeated literal maps to Start + Offset, where Start
% is the first slot of its mode. theta_sigma(Id) with theta_sigma_offset(Id,
% Section, Slot, Offset) lists every offset combination; they depend on no
% model, so "some combination is a consistent substitution avoiding O" is
% stratified negation and no disjunction is needed.

theta_group_start(Section, Slot, Start) :-
    theta_sigma_section(Section), theta_repeated(Section, Slot),
    selected(Section, Slot, Mode),
    Start = #min { Other : selected(Section, Other, Mode) }.

theta_target(Id, Section, Slot, Target) :-
    theta_sigma_offset(Id, Section, Slot, Offset),
    theta_group_start(Section, Slot, Start),
    Target = Start + Offset,
    selected(Section, Slot, Mode), selected(Section, Target, Mode).

theta_bad(Id) :-
    theta_sigma_offset(Id, Section, Slot, _), theta_group_start(Section, Slot, _),
    not theta_target(Id, Section, Slot, _).

theta_image(Id, Var, Image) :-
    theta_target(Id, Section, Slot, Target),
    var_at(Section, Slot, Position, Var),
    var_at(Section, Target, Position, Image).

theta_bad(Id) :- theta_image(Id, Var, Image), theta_fixed(Var), Image != Var.
theta_bad(Id) :- theta_image(Id, Var, Image), theta_image(Id, Var, Other), Image < Other.

theta_uses(Id, Section, Target) :- theta_target(Id, Section, _, Target).

theta_witness :-
    theta_sigma_section(Section), theta_repeated(Section, Omitted),
    theta_sigma(Id), not theta_bad(Id), not theta_uses(Id, Section, Omitted).

:- theta_witness.

% Saturation fallback for many offset combinations. theta_map guesses the image
% of every variable; theta_unfolded saturates when the guess is not a
% substitution folding the clause without Omitted. The saturated interpretation
% is stable exactly when no substitution exists: a witness defeats minimality.
% This makes the program disjunctive, so Python uses it only when enumerating
% offsets would ground too much.

theta_omission(Section, Omitted) :-
    theta_saturated_section(Section), theta_repeated(Section, Omitted).

theta_variable(Var) :-
    theta_saturated_section(_), theta_active, var_at(_, _, _, Var).

theta_map(OS, O, Var, Image) | theta_not_map(OS, O, Var, Image) :-
    theta_omission(OS, O), theta_variable(Var), theta_variable(Image).
theta_map(OS, O, Var, Image) : theta_variable(Image) :-
    theta_omission(OS, O), theta_variable(Var).

theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_map(OS, O, Var, Image), theta_not_map(OS, O, Var, Image).
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_map(OS, O, Var, Image), theta_map(OS, O, Var, Other),
    Image != Other.
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_map(OS, O, Var, Image), theta_fixed(Var), Image != Var.

theta_candidate(OS, O, Section, Source, Target) :-
    theta_omission(OS, O), theta_repeated(Section, Source),
    selected(Section, Source, Mode), selected(Section, Target, Mode),
    (Section, Target) != (OS, O).
theta_mismatch(OS, O, Section, Source, Target) :-
    theta_candidate(OS, O, Section, Source, Target),
    var_at(Section, Source, Position, Var),
    var_at(Section, Target, Position, Image),
    theta_not_map(OS, O, Var, Image).
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_repeated(Section, Source),
    theta_mismatch(OS, O, Section, Source, Target) :
        theta_candidate(OS, O, Section, Source, Target).

theta_map(OS, O, Var, Image) :-
    theta_unfolded(OS, O), theta_variable(Var), theta_variable(Image).
theta_not_map(OS, O, Var, Image) :-
    theta_unfolded(OS, O), theta_variable(Var), theta_variable(Image).

:- theta_omission(OS, O), not theta_unfolded(OS, O).
