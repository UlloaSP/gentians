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
%
% Every predicate of this file is a local helper: no other module uses it.

% DEFINITION, local helper. theta_movable(Mode, body): literals of Mode may be
% mapped onto one another by a substitution.
%   Mode  id of a plain atom template of the body, of either polarity, whose
%         recall allows more than one occurrence.
%   body  the section; only body atoms move.
% With recall 1 no clause repeats the mode, so nothing about it is grounded.
theta_movable(Mode, body) :-
    mode_section(Mode, body), normal_mode(Mode), mode_recall(Mode, Recall), Recall > 1.

% DEFINITION, local helper. theta_section(Section): theta reduction is active
% for that section, under either encoding.
%   Section  body, when Python emitted theta_sigma_section(body) (enumerated
%            offsets) or theta_saturated_section(body) (saturation). With
%            neither fact the whole file is inert.
% Case 1: the enumerated-offset encoding.
theta_section(Section) :- theta_sigma_section(Section).
% DEFINITION, local helper. Same predicate. Case 2: the saturation encoding.
theta_section(Section) :- theta_saturated_section(Section).

% Only a clause repeating a movable mode can be theta-redundant.
% DEFINITION, local helper. theta_repeated(Section, Slot): the literal at that
% slot is a candidate to move or to be dropped.
%   Section  the theta section (body).
%   Slot     slot of a movable literal whose mode is also selected at another
%            slot. In "p(X,Y), p(X,Z), o(Y)" with both modes repeatable, the
%            two p literals are repeated and o(Y) is not.
theta_repeated(Section, Slot) :-
    theta_section(Section),
    selected(Section, Slot, Mode), theta_movable(Mode, Section),
    selected(Section, Other, Mode), Slot != Other.
% DEFINITION, local helper. theta_active: the current clause repeats at least
% one movable literal. It has no arguments; it switches on the rest of the
% check for this model.
theta_active :- theta_repeated(_, _).

% DEFINITION, local helper. theta_fixed(Var): any substitution must map Var
% to itself.
%   Var  variable id that occurs in a literal that does not move: the head, a
%        comparison, arithmetic, an aggregate, a conditional, or an atom whose
%        mode is selected only once.
theta_fixed(Var) :-
    theta_active, var_at(Section, Slot, _, Var), not theta_repeated(Section, Slot).

% Enumerated offsets (a normal program). Equal modes occupy contiguous slots
% (symmetry/slots.lp), so a repeated literal maps to Start + Offset, where Start
% is the first slot of its mode. theta_sigma(Id) with theta_sigma_offset(Id,
% Section, Slot, Offset) lists every offset combination; they depend on no
% model, so "some combination is a consistent substitution avoiding O" is
% stratified negation and no disjunction is needed.
%
% Consistency is checked per move and per pair of moves, never per Id and
% variable: a combination is a substitution iff each move keeps fixed variables
% and every two moves agree on the image of each shared variable. Only these
% slot-level verdicts are joined with the offset combinations, so the ground
% size no longer multiplies the combinations by variables and images.

% DEFINITION, local helper. theta_group_start(Section, Slot, Start): where the
% run of literals sharing the mode of Slot begins.
%   Section  the theta section, under the enumerated-offset encoding.
%   Slot     slot of a repeated literal.
%   Start    the smallest slot holding the same mode. In "p, p, p, o, o" at
%            slots 0..4, every p has Start 0 and every o has Start 3.
theta_group_start(Section, Slot, Start) :-
    theta_sigma_section(Section), theta_repeated(Section, Slot),
    selected(Section, Slot, Mode),
    Start = #min { Other : selected(Section, Other, Mode) }.

% DEFINITION, local helper. theta_offset(Section, Offset): an offset value
% that Python enumerated.
%   Section  the theta section.
%   Offset   integer from 0 up to the largest mode group the body can hold,
%            minus one.
theta_offset(Section, Offset) :- theta_sigma_offset(_, Section, _, Offset).

% theta_move(Section, Slot, Offset, Target): Offset sends Slot onto Target.
% DEFINITION, local helper.
%   Section  the theta section.
%   Slot     slot of a repeated literal, the source of the move.
%   Offset   the offset applied to it.
%   Target   Start + Offset, accepted only when it holds the same mode as
%            Slot (it stays inside the group). Target = Slot is the identity
%            move.
theta_move(Section, Slot, Offset, Target) :-
    theta_group_start(Section, Slot, Start), theta_offset(Section, Offset),
    Target = Start + Offset,
    selected(Section, Slot, Mode), selected(Section, Target, Mode).

% theta_image(Section, Slot, Offset, Position, Image): after that move, the
% variable at Position of Slot becomes Image.
% DEFINITION, local helper.
%   Section, Slot, Offset  the move.
%   Position               a placeholder position of the literal.
%   Image                  variable id the target literal holds at the same
%                          position. Moving p(X,Z) onto p(X,Y) gives image X
%                          at position 0 and image Y at position 1.
theta_image(Section, Slot, Offset, Position, Image) :-
    theta_move(Section, Slot, Offset, Target),
    var_at(Section, Target, Position, Image).

% A move is blocked when Offset leaves the group or moves a fixed variable.
% DEFINITION, local helper. theta_blocked(Section, Slot, Offset): that move is
% not allowed on its own.
%   Section, Slot  a repeated literal.
%   Offset         an enumerated offset.
% Case 1: Start + Offset is not a slot of the same mode.
theta_blocked(Section, Slot, Offset) :-
    theta_group_start(Section, Slot, _), theta_offset(Section, Offset),
    not theta_move(Section, Slot, Offset, _).
% DEFINITION, local helper. Same predicate. Case 2: the move would send a
% fixed variable to a different variable.
%   Position  placeholder of Slot that holds the fixed variable Var.
theta_blocked(Section, Slot, Offset) :-
    theta_move(Section, Slot, Offset, _),
    var_at(Section, Slot, Position, Var), theta_fixed(Var),
    not theta_image(Section, Slot, Offset, Position, Var).

% theta_shared(Section, Slot, Position, Other, OtherPosition): two positions of
% repeated literals hold the same variable, ordered to list each pair once.
% DEFINITION, local helper.
%   Section         the theta section.
%   Slot, Position  a placeholder of a repeated literal.
%   Other, OtherPosition
%                   a later placeholder, of the same or of another repeated
%                   literal, that holds the same variable.
theta_shared(Section, Slot, Position, Other, OtherPosition) :-
    theta_repeated(Section, Slot), theta_repeated(Section, Other),
    var_at(Section, Slot, Position, Var), var_at(Section, Other, OtherPosition, Var),
    (Slot, Position) < (Other, OtherPosition).

% Two moves clash when they send one variable to different images.
% DEFINITION, local helper. theta_clash(Section, Slot, Offset, Other,
% OtherOffset): the two moves cannot belong to one substitution.
%   Section         the theta section.
%   Slot, Offset    a move of one repeated literal.
%   Other, OtherOffset
%                   a move of a literal sharing a variable with it (possibly
%                   the same literal, at another position). The shared
%                   variable gets one image from the first move and a
%                   different one, or none, from the second.
theta_clash(Section, Slot, Offset, Other, OtherOffset) :-
    theta_shared(Section, Slot, Position, Other, OtherPosition),
    theta_image(Section, Slot, Offset, Position, Image),
    theta_offset(Section, OtherOffset),
    not theta_image(Section, Other, OtherOffset, OtherPosition, Image).

% DEFINITION, local helper. theta_bad(Id): offset combination Id is not a
% substitution of the current clause.
%   Id  id of one combination enumerated by Python; theta_sigma_offset(Id,
%       Section, Slot, Offset) gives the offset it assigns to each body slot.
% Case 1: it assigns a blocked move to some repeated literal.
theta_bad(Id) :-
    theta_sigma_offset(Id, Section, Slot, Offset), theta_blocked(Section, Slot, Offset).
% DEFINITION, local helper. Same predicate. Case 2: two of its moves clash.
theta_bad(Id) :-
    theta_sigma_offset(Id, Section, Slot, Offset),
    theta_sigma_offset(Id, Section, Other, OtherOffset), Slot <= Other,
    theta_clash(Section, Slot, Offset, Other, OtherOffset).

% DEFINITION, local helper. theta_uses(Id, Section, Target): combination Id
% maps some repeated literal onto Target.
%   Id       id of the offset combination.
%   Section  the theta section.
%   Target   a slot that is the image of at least one literal; a slot that
%            no literal maps to is dropped by the substitution.
theta_uses(Id, Section, Target) :-
    theta_sigma_offset(Id, Section, Slot, Offset), theta_move(Section, Slot, Offset, Target).

% DEFINITION, local helper. theta_witness: some offset combination is a valid
% substitution that leaves a repeated literal without preimage. It has no
% arguments: one witness is enough to condemn the clause.
%   Omitted  (body variable) slot of the repeated literal that gets dropped.
%   Id       (body variable) the combination that proves it.
theta_witness :-
    theta_sigma_section(Section), theta_repeated(Section, Omitted),
    theta_sigma(Id), not theta_bad(Id), not theta_uses(Id, Section, Omitted).

% CONSTRAINT (enumerated-offset encoding). Reject a clause that a substitution
% folds onto a proper subclause of itself: it is equivalent to that shorter
% clause, which is enumerated on its own.
%   pruned: q(X) :- p(X,Y), p(X,Z).       Z -> Y drops p(X,Z); q(X) :- p(X,Y)
%                                         says the same
%   kept:   q(X) :- p(X,Y), p(Y,Z).       no substitution drops an atom
%   kept:   q(Y) :- p(X,Y), p(X,Z), Y != Z.   Z is fixed by the comparison
:- theta_witness.

% Saturation fallback for many offset combinations. theta_map guesses the image
% of every variable; theta_unfolded saturates when the guess is not a
% substitution folding the clause without Omitted. The saturated interpretation
% is stable exactly when no substitution exists: a witness defeats minimality.
% This makes the program disjunctive, so Python uses it only when enumerating
% offsets would ground too much.
%
% In the rules below (OS, O) names the literal being omitted: OS is its
% section and O its slot.

% DEFINITION, local helper. theta_omission(Section, Omitted): one subproblem
% of the saturation check, "is there a substitution that drops this literal?".
%   Section  the theta section, under the saturation encoding.
%   Omitted  slot of a repeated literal.
theta_omission(Section, Omitted) :-
    theta_saturated_section(Section), theta_repeated(Section, Omitted).

% DEFINITION, local helper. theta_variable(Var): Var takes part in the
% guessed substitution.
%   Var  any variable id used in the clause, as soon as the check is active
%        under the saturation encoding. It serves as both source and image.
theta_variable(Var) :-
    theta_saturated_section(_), theta_active, var_at(_, _, _, Var).

% CHOICE (disjunctive guess). For each omission and each pair of variables,
% either the substitution maps Var to Image or it does not.
%   OS, O  the omitted literal (section, slot).
%   Var    source variable id.
%   Image  candidate image variable id.
%   theta_map      the guess "Var is sent to Image".
%   theta_not_map  its explicit complement, needed because saturation cannot
%                  use default negation on the guessed atoms.
theta_map(OS, O, Var, Image) | theta_not_map(OS, O, Var, Image) :-
    theta_omission(OS, O), theta_variable(Var), theta_variable(Image).
% DEFINITION, local helper (disjunctive). Every variable has at least one
% image: the head is the disjunction of theta_map(OS, O, Var, Image) over all
% candidate images.
theta_map(OS, O, Var, Image) : theta_variable(Image) :-
    theta_omission(OS, O), theta_variable(Var).

% DEFINITION, local helper. theta_unfolded(OS, O): the current guess fails to
% be a substitution that drops literal (OS, O).
%   OS, O  the omitted literal (section, slot).
% Case 1: the guess is incoherent, Var both mapped and not mapped to Image.
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_map(OS, O, Var, Image), theta_not_map(OS, O, Var, Image).
% DEFINITION, local helper. Same predicate. Case 2: the guess is not a
% function, Var has two different images.
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_map(OS, O, Var, Image), theta_map(OS, O, Var, Other),
    Image != Other.
% DEFINITION, local helper. Same predicate. Case 3: the guess moves a fixed
% variable.
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_map(OS, O, Var, Image), theta_fixed(Var), Image != Var.

% DEFINITION, local helper. theta_candidate(OS, O, Section, Source, Target):
% a literal that Source may be mapped onto while (OS, O) is omitted.
%   OS, O    the omitted literal.
%   Section  section of the source literal.
%   Source   slot of a repeated literal.
%   Target   a slot of the same mode, other than the omitted one. It may be
%            Source itself.
theta_candidate(OS, O, Section, Source, Target) :-
    theta_omission(OS, O), theta_repeated(Section, Source),
    selected(Section, Source, Mode), selected(Section, Target, Mode),
    (Section, Target) != (OS, O).
% DEFINITION, local helper. theta_mismatch(OS, O, Section, Source, Target):
% the guess does not send Source onto that candidate Target.
%   Arguments as in theta_candidate/5.
% It holds when, at some placeholder position, the guess does not map the
% variable of Source to the variable of Target.
theta_mismatch(OS, O, Section, Source, Target) :-
    theta_candidate(OS, O, Section, Source, Target),
    var_at(Section, Source, Position, Var),
    var_at(Section, Target, Position, Image),
    theta_not_map(OS, O, Var, Image).
% DEFINITION, local helper. theta_unfolded, case 4: some repeated literal
% Source has no image at all: the guess mismatches every one of its
% candidates (the conditional literal in the body ranges over all of them).
theta_unfolded(OS, O) :-
    theta_omission(OS, O), theta_repeated(Section, Source),
    theta_mismatch(OS, O, Section, Source, Target) :
        theta_candidate(OS, O, Section, Source, Target).

% DEFINITION, local helper (saturation). Once a guess has failed, make every
% theta_map atom of that omission true.
%   OS, O       the omission whose guess failed.
%   Var, Image  every pair of variables.
% All failed guesses thereby collapse into one maximal interpretation, which
% is stable only if no smaller, successful guess exists.
theta_map(OS, O, Var, Image) :-
    theta_unfolded(OS, O), theta_variable(Var), theta_variable(Image).
% DEFINITION, local helper (saturation). The same for every theta_not_map
% atom of that omission.
theta_not_map(OS, O, Var, Image) :-
    theta_unfolded(OS, O), theta_variable(Var), theta_variable(Image).

% CONSTRAINT (saturation encoding). Every omission must end saturated. If a
% substitution dropping (OS, O) exists, the saturated interpretation is not
% minimal, and the only other candidate models have theta_unfolded(OS, O)
% false and are rejected here: the clause has no model. It prunes and keeps
% exactly the clauses of the enumerated-offset constraint above.
%   pruned: q(X) :- p(X,Y), p(X,Z).
%   kept:   q(X) :- p(X,Y), p(Y,Z).
:- theta_omission(OS, O), not theta_unfolded(OS, O).
