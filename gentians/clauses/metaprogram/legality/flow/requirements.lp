% Reject unmet inputs and outputs after the positive fixed point.
% Default-negated and conditional literals never produce global variables.
%
% The examples assume these declarations unless they state others:
%   #modeh(1,target(var(node,input),var(node,output))).
%   #modeb(2,edge(var(node,input),var(node,output))).

% CONSTRAINT. A clause-global variable at an input position of a conditional
% literal must be flow_bound.
%   Var  such a variable id.
% With #modeb(1,ok(var(node,input)):node(var(node,any))); V0 is global in
% both clauses because it also occurs in edge:
%   pruned: :- edge(V0,V1), ok(V0) : node(V2).                  no seed binds V0
%   kept:   target(V0,V1) :- edge(V0,V1), ok(V0) : node(V2).    V0 is a head input
:- conditional_global_input_var(Var), not flow_bound(Var).

% CONSTRAINT. A clause-global variable at an output position of a body
% conditional must be produced by another literal; the conditional itself
% produces nothing.
%   Var  such a variable id.
% With #modeb(1,reach(var(node,output)):node(var(node,any))):
%   pruned: target(V0,V1) :- reach(V1) : node(V2).     V1 is global via the
%                                                      head; nothing produces it
%   kept:   target(V0,V1) :- edge(V0,V1), reach(V1) : node(V2).   edge produces V1
:- conditional_global_output_var(body, Var), not flow_produced(Var).

% A head output is also satisfied by an input position of the same head.
% CONSTRAINT. A clause-global variable at an output position of a head
% conditional must be produced by the body or be a head input.
%   Var  such a variable id.
% With #modeh(1,mark(var(node,output)):node(var(node,any))),
% #modeb(1,seen(var(node,any))) and #modeb(1,start(var(node,output))); V0 is
% global in both clauses because it also occurs in the body:
%   pruned: mark(V0) : node(V1) :- seen(V0).     "any" binds V0 without producing it
%   kept:   mark(V0) : node(V1) :- start(V0).    start outputs V0
:- conditional_global_output_var(head, Var),
    not flow_produced(Var),
    not head_input_var(Var).

% CONSTRAINT. Every selected arithmetic literal must become ready: both
% operands flow_bound.
%   Slot  body slot of the arithmetic literal.
% With #modeb(1,num(var(numeric,any))):
%   pruned: :- num(V0), V0+V1=V2.           V1 is never bound
%   kept:   :- num(V0), num(V1), V0+V1=V2.
:- selected(body, Slot, Mode), arithmetic_mode(Mode), not ready_arithmetic(Slot).

% CONSTRAINT. Every variable a comparison reads (a non-output placeholder)
% must be flow_bound.
%   Slot, Arg  the comparison placeholder.
%   Var        variable id written there.
% With #modeb(1,num(var(numeric,any))):
%   pruned: :- num(V0), V0 < V1.            V1 is never bound
%   kept:   :- num(V0), num(V1), V0 < V1.
:- selected(body, Slot, Mode),
    comparison_mode(Mode),
    var_at(body, Slot, Arg, Var),
    not mode_arg_direction(Mode, Arg, output),
    not flow_bound(Var).

% CONSTRAINT. Every selected value-producing comparison must become ready:
% all its non-output placeholders flow_bound.
%   Slot  body slot of the comparison.
% With #modeb(1,num(var(numeric,any))) and an assigning comparison rendered
% "V1 = V0 + 1", whose left side is declared output and right side input:
%   pruned: :- V1 = V0 + 1.                 V0 is never bound
%   kept:   :- num(V0), V1 = V0 + 1.
:- selected(body, Slot, Mode),
   relation_output_mode(Mode),
   not ready_relation(Slot).

% CONSTRAINT. Every selected directed body literal must become ready: all its
% input positions flow_bound.
%   Slot  body slot of the directed literal.
%   pruned: target(V0,V1) :- edge(V2,V1).                V2 is never bound
%   pruned: :- edge(V0,V1), edge(V1,V0).                 an unseeded input cycle
%   kept:   target(V0,V1) :- edge(V0,V1).                V0 is a head input
%   kept:   target(V0,V1) :- edge(V0,V2), edge(V2,V1).   a chain from V0
:- selected(body, Slot, Mode), directed_mode(Mode), not ready_literal(Slot).

% CONSTRAINT. Every output position of a non-conditional head literal must be
% produced by the body or coincide with a head input.
%   Slot, Arg  the head placeholder declared output.
%   Var        variable id written there.
%   pruned: target(V0,V1) :- edge(V0,V2).   V1 is never produced
%   kept:   target(V0,V1) :- edge(V0,V1).   edge produces V1
%   kept:   target(V0,V0) :- edge(V0,V1).   V0 is an input of the same head
:- selected(head, Slot, Mode),
    not conditional_mode(Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(head, Slot, Arg, Var),
    not flow_produced(Var),
    not head_input_var(Var).
