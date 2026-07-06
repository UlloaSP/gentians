% Closed-world universal predicate property.
%
% Python emits universal_pred(Pred) when predicate Pred is true for every tuple
% in its observed typed domain. Positive universal literals are redundant when
% all their variables are already guarded elsewhere; negative universal literals
% are impossible. For binary predicates, universal truth also implies
% reflexivity, so this file exports reflexive_pred/1 instead of asking Python
% to emit both properties.
%
% Shared atom shapes used here:
% - universal_pred(Pred): property fact.
% - reflexive_pred(Pred): derived property atom consumed by reflexive.lp.
% - mode(Section,Mode,Pred,Arity,Recall): Python fact used only to know whether
%   Pred is binary.
% - positive_body_literal/4 and negative_body_literal/4: selected body atoms.
% - var_at(body,Slot,Arg,Var): variable in literal Slot.
% - positive_body_var_outside_slot(Slot,Var): Var is grounded by another
%   positive body literal outside Slot.

% Python fact contract:
% - universal_pred(Pred): emitted by Python when predicate id Pred is true for
%   every tuple in its observed typed domain.
% - mode(Section,Mode,Pred,Arity,Recall): emitted by Python for every available
%   hypothesis mode. Arity=2 means Pred is binary and can be reflexive.
% Python fact detail: universal_pred(Pred) marks predicate id Pred as true for every tuple in observed typed domain.
#defined universal_pred/1.
% Python fact detail: mode(Section,Mode,Pred,Arity,Recall) is emitted per hypothesis mode; Arity identifies binary predicates for reflexive derivation.
#defined mode/5.

% Rule: binary universal predicates are reflexive.
% Pred is a predicate id. mode/5 supplies Arity=2, because reflexivity is only
% meaningful for binary predicates. reflexive.lp owns self-pair pruning.
reflexive_pred(Pred):-
    universal_pred(Pred),
    mode(_,_,Pred,2,_).

% Rule: detect a universal positive literal with at least one unguarded variable.
% Slot is positive universal body literal. Var is one variable in that literal.
% If Var does not occur in another positive body literal, the universal atom may
% still act as a domain guard and should not be pruned by the next constraint.
universal_literal_missing_guard(Slot):-
    positive_body_literal(Slot,_,Pred,_),
    universal_pred(Pred),
    var_at(body,Slot,_,Var),
    not positive_body_var_outside_slot(Slot,Var).

% Constraint: reject guarded positive universal literals.
% Slot is positive body literal for universal Pred. If no missing guard exists,
% every variable in the literal is already grounded elsewhere, so the universal
% literal is always true and redundant.
:- positive_body_literal(Slot,_,Pred,_),
    universal_pred(Pred),
    not universal_literal_missing_guard(Slot).

% Constraint: reject negative universal literals.
% not Pred(...) can never hold when Pred is true for every typed-domain tuple.
:- negative_body_literal(Slot,_,Pred,_),
    universal_pred(Pred).
