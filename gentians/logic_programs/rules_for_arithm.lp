% Reglas especificas para stubs con operadores aritmeticos.
%
% Python emite:
% - arithm_term_position(C,P): posiciones de operandos de la expresion C.
%   En X + Y = Z, normalmente X e Y son operandos.
% - result_term_position(C,P): posicion del resultado de la expresion C.
%   En X + Y = Z, Z es resultado.
% - all_arithm_term_position(C,P): cualquier posicion de esa expresion,
%   operandos y resultado.

% Una variable se considera "no solo aritmetica" si aparece al menos en una
% posicion que no pertenece a ningun termino aritmetico. Puede ser un atomo
% normal, agregado o comparacion, segun el stub.
var_not_in_arithm(Var):-
    var_pos(Var,Pos),
    not all_arithm_term_position(_,Pos).

% Descarta variables cuyo unico uso esta dentro de posiciones aritmeticas.
% Esto evita reglas inseguras o poco informativas como usar X solo en X + Y = Z
% sin que X este conectado con ningun literal de la regla.
:- var_pos(Var,Pos), all_arithm_term_position(_,Pos), not var_not_in_arithm(Var).

% Dentro de una misma expresion aritmetica C, un operando y el resultado no
% pueden recibir la misma variable. Para X + Y = Z elimina asignaciones como
% X + Y = X. La comparacion P0 != P1 evita comparar una posicion consigo misma.
:-  arithm_term_position(C,P0),
    result_term_position(C,P1),
    P0 != P1,
    var_pos(Var0,P0),
    var_pos(Var1,P1),
    Var0 == Var1.
