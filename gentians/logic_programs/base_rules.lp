% Base comun para cualquier stub de regla.
%
% El programa Python crea antes estos hechos:
% - var(0..N): identificadores de variables candidatas, que luego se imprimen
%   como V0, V1, ...
% - pos(0..M): posiciones donde habia un hueco "_____" en el stub original.
% - last_index_var_in_head(I): ultima posicion que pertenece a la cabeza.
%
% Este archivo decide la relacion principal var_pos(Var,Pos). Cada answer set
% representa una asignacion completa de variables a posiciones; despues Python
% reconstruye la regla reemplazando cada hueco por la variable asignada.

% Para cada posicion Pos debe elegirse exactamente una variable Var.
% La choice rule "1{...}1" enumera todas las variables posibles para esa
% posicion y fuerza cardinalidad exacta 1. Sin esta regla no habria asignacion
% completa de variables; con cardinalidad mayor que 1 una misma posicion podria
% recibir varias variables incompatibles.
1{var_pos(Var,Pos) : var(Var)}1:- pos(Pos).

% Seguridad de variables de cabeza:
% la comprobacion general depende de si hay agregados, aritmetica o
% comparaciones. Por eso no vive aqui: se anade desde
% rules_for_aggregates_arithm_comparison.lp o rules_only_standard_atoms.lp.

% Marca una variable como usada al menos dos veces si aparece en dos posiciones
% distintas P0 y P1. P0 != P1 evita contar dos veces el mismo hueco.
at_least_twice(V):- var_pos(V,P0), var_pos(V,P1), P0 != P1.

% Descarta todo answer set donde alguna variable elegida aparece una sola vez.
% Esto evita variables "sueltas" que no conectan literales, resultados,
% comparaciones o agregados. Tambien obliga a que resultados calculados se usen
% en algun otro lugar de la regla.
:- var_pos(V,_), not at_least_twice(V).

% Elimina huecos en la numeracion de variables.
% Si Var1 (por ejemplo V2) se usa, entonces toda variable con indice menor
% Var0 (por ejemplo V0 o V1) debe usarse tambien. Esto rompe simetrias:
% asignaciones iguales salvo por renombrado, como usar V1 en vez de V0, no se
% generan como soluciones separadas.
:- var(Var0), var(Var1), Var0 < Var1, not var_pos(Var0,_), var_pos(Var1,_).

% Fija V0 en la primera posicion. Es otra rotura de simetria: como los nombres
% de variables son intercambiables, siempre puede renombrarse una solucion para
% que la primera variable sea V0. La constraint elimina las variantes
% equivalentes donde la posicion 0 recibia V1, V2, etc.
:- not var_pos(0,0).

% Identifica posiciones que pertenecen a atomos "normales" de la regla.
% Una posicion cuenta como atomica si existe en pos(Pos) y no esta marcada como
% parte de una comparacion ni como parte de un termino aritmetico. Es decir,
% huecos dentro de literales como p(_), q(_,_) cuentan; huecos de X < Y o
% X + Y = Z no cuentan aqui.
atom_pos(Pos):-
    pos(Pos),
    not comparison_term_position(_,Pos),
    not all_arithm_term_position(_,Pos).

% Exige que la regla tenga al menos un atomo normal.
% Sin esta constraint, podrian sobrevivir stubs formados solo por expresiones
% aritmeticas/comparaciones, que no dan soporte relacional suficiente al
% aprendizaje de reglas ASP.
:- not atom_pos(_).
