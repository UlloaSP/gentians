% Closed-world single-input functional dependency property.
%
% Python emits functional_pred(Pred,Input,Output) when predicate Pred maps each
% value at argument Input to only one value at argument Output. This file prunes
% conflicting positive pairs and contradictory positive/negative pairs.
%
% Shared atom shapes used here:
% - functional_pred(Pred,Input,Output): property fact. Pred is predicate id;
%   Input and Output are zero-based argument indexes.
% - positive_body_literal/4 and negative_body_literal/4: selected body atoms.
% - var_at(body,Slot,Arg,Var): variable at predicate argument Arg.
% - known_distinct_vars(Out0,Out1): outputs are proven different.

#defined functional_pred/3.

% Constraint: reject two positive facts with same input and different outputs.
% Slot0 and Slot1 are ordered positive literals for Pred. Same is the shared
% input variable at Input. Out0 and Out1 are variables at Output. If outputs
% differ, functional dependency is violated.
:- positive_body_literal(Slot0,_,Pred,_),
    positive_body_literal(Slot1,_,Pred,_),
    Slot0 < Slot1,
    functional_pred(Pred,Input,Output),
    var_at(body,Slot0,Input,Same),
    var_at(body,Slot1,Input,Same),
    var_at(body,Slot0,Output,Out0),
    var_at(body,Slot1,Output,Out1),
    Out0 != Out1.

% Constraint: reject negative fact contradicted by positive functional fact.
% PosSlot and NegSlot use same Pred and same Input variable Same. If Output
% variables are known distinct, the negative literal is implied by functionality
% and should not be generated.
:- positive_body_literal(PosSlot,_,Pred,_),
    negative_body_literal(NegSlot,_,Pred,_),
    functional_pred(Pred,Input,Output),
    var_at(body,PosSlot,Input,Same),
    var_at(body,NegSlot,Input,Same),
    var_at(body,PosSlot,Output,Out0),
    var_at(body,NegSlot,Output,Out1),
    known_distinct_vars(Out0,Out1).
