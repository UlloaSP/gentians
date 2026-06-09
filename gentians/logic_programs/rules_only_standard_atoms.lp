% Reglas para stubs formados solo por atomos normales.
%
% Se usa este archivo cuando no hay agregados, aritmetica ni comparaciones.
% En ese caso, la seguridad clasica de ASP basta: toda variable que aparece en
% la cabeza debe aparecer tambien en el cuerpo positivo.

% Variable presente en la cabeza.
% last_index_var_in_head(I) separa posiciones: P <= I pertenece a la cabeza.
v_in_head(V):- last_index_var_in_head(I), var_pos(V,P), P <= I.

% Variable presente en el cuerpo.
% P > I significa que la posicion esta despues de ":-" en el stub original.
v_in_body(V):- last_index_var_in_head(I), var_pos(V,P), P > I.

% Descarta reglas inseguras: si una variable aparece en la cabeza pero nunca en
% el cuerpo, clingo no puede acotarla mediante literales del cuerpo. Ejemplo
% eliminado: p(V0) :- q(V1).
:- v_in_head(V), not v_in_body(V).
