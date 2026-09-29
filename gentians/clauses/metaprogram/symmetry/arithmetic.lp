% Order operands only for modes whose types, directions and labels allow
% interchange. Specialized flags are emitted by the mode compiler.
%
% A commutative mode keeps only the ascending operand-id orientation:
%   kept:   V0+V1=V2    V0*V1=V2    |V0-V1|=V2    V0+V0=V1 (equal ids)
%   pruned: V1+V0=V2    V1*V0=V2    |V1-V0|=V2    (swapped copy of a kept one)
% Modes without a flag keep both orientations:
%   V0-V1=V2 and V1-V0=V2    operand order changes the value.
%   V0/V1=V2 and V1/V0=V2    div_mode is emitted but is not commutative.
%   var(numeric,input,a)+var(numeric,input,b)=...: both V0+V1=V2 and V1+V0=V2
%   survive because different labels make the operands non-interchangeable
%   and add_mode is not emitted; canonicalization merges them afterwards.

commutative_mode(Mode) :- add_mode(Mode).
commutative_mode(Mode) :- mul_mode(Mode).
commutative_mode(Mode) :- abs_mode(Mode).

:- selected(body,Slot,Mode), 
   commutative_mode(Mode),
   arithmetic_operand(Slot,left,Left), 
   arithmetic_operand(Slot,right,Right), 
   Left > Right.
