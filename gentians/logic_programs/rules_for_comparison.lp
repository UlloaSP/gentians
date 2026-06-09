% Reglas especificas para stubs con comparaciones.
%
% Python emite comparison_term_position(C,P) para cada lado de cada comparacion
% detectada. En X < Y, ambas posiciones X e Y pertenecen a la misma comparacion
% C. Estas reglas obligan a que esas variables esten conectadas con otros
% literales y que la comparacion no sea trivial.

% Una variable esta fuera de comparaciones si aparece en alguna posicion que no
% esta marcada como comparison_term_position. Esto da soporte a la variable en
% el resto de la regla.
var_not_in_comparison(Var):-
    var_pos(Var,Pos),
    not comparison_term_position(_,Pos).

% Descarta asignaciones donde una variable usada en una comparacion no aparece
% en ningun otro sitio. Ejemplo eliminado: regla con X < Y donde X o Y no sale
% tambien en un atomo/literal que pueda ligar su dominio.
:- var_pos(Var,Pos), comparison_term_position(_,Pos), not var_not_in_comparison(Var).

% Dentro de una misma comparacion C, los dos lados deben ser variables
% distintas. Elimina comparaciones tautologicas o contradictorias por forma,
% como X == X, X != X, X < X o X >= X, que no aportan una relacion util entre
% variables diferentes.
:- comparison_term_position(C,P0),
    comparison_term_position(C,P1),
    P0 != P1,
    var_pos(Var0,P0),
    var_pos(Var1,P1),
    Var0 == Var1.
