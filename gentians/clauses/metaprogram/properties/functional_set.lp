% Closed-world composite functional dependency property.
%
% Python emits functional_set_pred(Pred,Fd,Output) and functional_set_arg(Fd,Input)
% when a set of input arguments functionally determines one output argument.
% This file rejects two positive Pred literals with same determinant variables
% and different output variables, and rejects a negative Pred literal already
% excluded by a positive Pred literal plus the dependency.
%
% Shared atom shapes used here:
% - functional_set_pred(Pred,Fd,Output): property fact. Fd is dependency id.
% - functional_set_arg(Fd,Input): argument Input participates in determinant Fd.
% - positive_body_literal/4 and negative_body_literal/4: selected body atoms.
% - var_at(body,Slot,Arg,Var): variable assignment at predicate argument Arg.
% - known_distinct_vars(Out0,Out1): comparison module proves variables differ.

% Python fact contract:
% - functional_set_pred(Pred,Fd,Output): emitted by Python when composite
%   dependency id Fd for predicate id Pred determines zero-based Output arg.
%   Other ASP property files may also derive functional_set_pred/3 from stronger
%   properties such as keys.
% - functional_set_arg(Fd,Input): emitted by Python for every zero-based input
%   argument participating in composite dependency Fd. Other ASP property files
%   may also derive functional_set_arg/2.
% Python fact detail: functional_set_pred(Pred,Fd,Output) says composite dependency Fd determines Output for Pred.
#defined functional_set_pred/3.
% Python fact detail: functional_set_arg(Fd,Input) lists one determinant argument Input for dependency Fd.
#defined functional_set_arg/2.

% Rule: two candidate literals differ on at least one determinant input.
% Slot0 and Slot1 are positive literals being compared. Fd is composite
% dependency id. Input is one determinant argument. In0 and In1 are variables at
% that argument. Difference means the FD does not require equal outputs.
fd_inputs_differ(Slot0,Slot1,Fd):-
    functional_set_arg(Fd,Input),
    var_at(body,Slot0,Input,In0),
    var_at(body,Slot1,Input,In1),
    In0 != In1.

% Constraint: reject same determinant with different output.
% Slot0 and Slot1 are ordered positive literals of Pred. functional_set_pred
% supplies Fd and Output. not fd_inputs_differ proves all determinant inputs
% match. Out0 != Out1 violates the composite functional dependency.
:- positive_body_literal(Slot0,_,Pred,_),
    positive_body_literal(Slot1,_,Pred,_),
    Slot0 < Slot1,
    functional_set_pred(Pred,Fd,Output),
    not fd_inputs_differ(Slot0,Slot1,Fd),
    var_at(body,Slot0,Output,Out0),
    var_at(body,Slot1,Output,Out1),
    Out0 != Out1.

% Constraint: reject negative literal contradicted by the dependency.
% PosSlot is positive Pred tuple. NegSlot is not Pred with the same determinant
% inputs. Output is the determined argument. known_distinct_vars proves the
% positive and negative output variables cannot be equal, so the positive tuple
% already excludes the negative tuple.
:- positive_body_literal(PosSlot,_,Pred,_),
    negative_body_literal(NegSlot,_,Pred,_),
    functional_set_pred(Pred,Fd,Output),
    not fd_inputs_differ(PosSlot,NegSlot,Fd),
    var_at(body,PosSlot,Output,Out0),
    var_at(body,NegSlot,Output,Out1),
    known_distinct_vars(Out0,Out1).
