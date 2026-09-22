% Closed-world composite functional dependency property.
%
% Python emits functional_set_pred(Pred,Fd,Output) and functional_set_arg(Fd,Input)
% when a set of input arguments functionally determines one output argument.
% This file rejects two positive Pred literals with same determinant variables
% and different output variables, and rejects a negative Pred literal already
% excluded by a positive Pred literal plus the dependency.

#defined functional_set_pred/3.
#defined functional_set_arg/2.

fd_inputs_differ(Slot0,Slot1,Fd):-
    functional_set_arg(Fd,Input),
    var_at(body,Slot0,Input,In0),
    var_at(body,Slot1,Input,In1),
    In0 != In1.

:- positive_body_literal(Slot0,_,Pred,_),
    positive_body_literal(Slot1,_,Pred,_),
    Slot0 < Slot1,
    functional_set_pred(Pred,Fd,Output),
    not fd_inputs_differ(Slot0,Slot1,Fd),
    var_at(body,Slot0,Output,Out0),
    var_at(body,Slot1,Output,Out1),
    Out0 != Out1.

% A negative tuple with a provably different output is already implied by the positive tuple.

:- positive_body_literal(PosSlot,_,Pred,_),
    negative_body_literal(NegSlot,_,Pred,_),
    functional_set_pred(Pred,Fd,Output),
    not fd_inputs_differ(PosSlot,NegSlot,Fd),
    var_at(body,PosSlot,Output,Out0),
    var_at(body,NegSlot,Output,Out1),
    known_distinct_vars(Out0,Out1).
