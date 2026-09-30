% Order operands only for modes whose types, directions and labels allow
% interchange. add_mode, mul_mode and abs_mode name the operator of every
% complete template; interchangeable_operands says its operands may swap.
%
% A commutative mode keeps only the ascending operand-id orientation:
%   kept:   V0+V1=V2    V0*V1=V2    |V0-V1|=V2    V0+V0=V1 (equal ids)
%   pruned: V1+V0=V2    V1*V0=V2    |V1-V0|=V2    (swapped copy of a kept one)
% Modes without a flag keep both orientations:
%   V0-V1=V2 and V1-V0=V2    operand order changes the value.
%   V0/V1=V2 and V1/V0=V2    div_mode is emitted but is not commutative.
%   var(numeric,input,a)+var(numeric,input,b)=...: both V0+V1=V2 and V1+V0=V2
%   survive because different labels make the operands non-interchangeable;
%   canonicalization merges them afterwards.

% DEFINITION, local helper. commutative_mode(Mode): swapping the two operands
% of this arithmetic template yields the same literal of the same template.
%   Mode  id of a complete arithmetic template whose operator is commutative
%         and whose operands have equal type, direction and label
%         (interchangeable_operands).
% Used only by the constraint below.
% Case 1: addition.
commutative_mode(Mode) :- add_mode(Mode), interchangeable_operands(Mode).
% DEFINITION, local helper. Same predicate. Case 2: multiplication.
commutative_mode(Mode) :- mul_mode(Mode), interchangeable_operands(Mode).
% DEFINITION, local helper. Same predicate. Case 3: absolute difference
% |Left-Right|.
commutative_mode(Mode) :- abs_mode(Mode), interchangeable_operands(Mode).

% CONSTRAINT. A commutative arithmetic literal writes its operands in
% ascending variable-id order.
%   Slot   body slot of the literal.
%   Left   variable id of the left operand.
%   Right  variable id of the right operand.
%   pruned: :- n(V0), n(V1), V1+V0=V2, r(V2).
%   kept:   :- n(V0), n(V1), V0+V1=V2, r(V2).
%   kept:   :- n(V0), V0+V0=V1, r(V1).          equal ids are not "greater"
:- selected(body,Slot,Mode),
   commutative_mode(Mode),
   arithmetic_operand(Slot,left,Left),
   arithmetic_operand(Slot,right,Right),
   Left > Right.
