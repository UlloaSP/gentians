% Closed-world universal predicate property.
%
% Python emits universal_pred(Pred) when predicate Pred is true for every tuple
% in its observed typed domain. Positive universal literals are redundant when
% all their variables are already guarded elsewhere; negative universal literals
% are impossible.
%
% Shared atom shapes used here:
% - universal_pred(Pred): property fact.
% - positive_body_literal/4 and negative_body_literal/4: selected body atoms.
% - var_at(body,Slot,Arg,Var): variable in literal Slot.
% - positive_body_var_outside_slot(Slot,Var): Var is grounded by another
%   positive body literal outside Slot.

% Python fact contract:
% - universal_pred(Pred): emitted by Python when predicate id Pred is true for
%   every tuple in its observed typed domain.
% Python fact detail: universal_pred(Pred) marks predicate id Pred as true for every tuple in observed typed domain.
#defined universal_pred/1.

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
