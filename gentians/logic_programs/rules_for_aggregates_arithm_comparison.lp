% Reglas de seguridad cuando existen agregados, aritmetica o comparaciones.
%
% Este archivo sustituye a rules_only_standard_atoms.lp en stubs complejos.
% La idea base sigue siendo: toda variable de la cabeza debe aparecer en el
% cuerpo. Pero no cualquier aparicion en el cuerpo cuenta como soporte seguro:
% posiciones dentro de agregados, terminos aritmeticos y comparaciones se
% restan porque pueden no ligar la variable por si solas.

% Variable presente en el cuerpo sintactico.
% P > VHI significa que la posicion esta despues de la cabeza. Esta regla cuenta
% todas las apariciones de cuerpo, incluidas las que luego se descontaran.
v_body(V,P):-
    var_pos(V,P), 
    P > VHI, 
    last_index_var_in_head(VHI).

% Placeholder para que el predicado exista aunque el stub no tenga agregados.
% El valor negativo no coincide con posiciones reales, porque pos/1 empieza en
% 0. Sirve para evitar warnings de clingo por predicados no definidos.
aggregate_term_position(-1,-1).

% Aparicion de cuerpo que esta en la tupla de terminos de un agregado.
% Se cuenta aparte para restarla del total de apariciones de cuerpo seguras.
v_body_atp(V,P):-
    var_pos(V,P), 
    P > VHI, 
    last_index_var_in_head(VHI),
    aggregate_term_position(_,P).

% Placeholder equivalente para variables dentro del literal interno del
% agregado, despues de ":".
aggregate_atom_position(-2,-2).

% Aparicion de cuerpo dentro del atomo/literal interno de un agregado.
% Tambien se descuenta del cuerpo "normal" porque tiene alcance local al
% agregado y no debe, por si sola, justificar una variable de cabeza.
v_body_aap(V,P):-
    var_pos(V,P), 
    P > VHI, 
    last_index_var_in_head(VHI),
    aggregate_atom_position(_,P).

% Placeholder para operandos/resultados de expresiones aritmeticas.
arithm_term_position(-3,-3).

% Aparicion de cuerpo dentro de una expresion aritmetica. Se descuenta porque
% aritmetica como X + Y = Z no liga dominios por si misma si X/Y/Z no aparecen
% tambien en literales normales.
v_body_arp(V,P):-
    var_pos(V,P), 
    P > VHI, 
    last_index_var_in_head(VHI),
    arithm_term_position(_,P).

% Placeholder para lados de comparaciones.
comparison_term_position(-4,-4).

% Aparicion de cuerpo dentro de comparacion. Se descuenta porque comparaciones
% como X < Y restringen variables, pero no introducen su dominio si no aparecen
% tambien en literales normales.
v_body_ctp(V,P):-
    var_pos(V,P), 
    P > VHI, 
    last_index_var_in_head(VHI),
    comparison_term_position(_,P).


% Calcula cuantas apariciones "seguras" tiene Var en el cuerpo.
% CT cuenta todas las posiciones de cuerpo donde aparece Var.
% CATP descuenta posiciones de tupla de agregado.
% CAAP descuenta posiciones de atomos internos de agregado.
% CARP descuenta posiciones aritmeticas.
% CCOMP descuenta posiciones de comparacion.
% Resultado: C = apariciones de cuerpo que estan en literales normales y pueden
% servir como soporte para variables de cabeza.
cv_body(Var,C):-
    CT = #count{P : v_body(Var,P)},
    CATP = #count{P : v_body_atp(Var,P)},
    CAAP = #count{P : v_body_aap(Var,P)},
    CARP = #count{P : v_body_arp(Var,P)},
    CCOMP = #count{P : v_body_ctp(Var,P)},
    var(Var),          
    C = CT - CATP - CAAP - CARP - CCOMP.


% Cuenta cuantas veces aparece Var en la cabeza.
% Pos <= VHI selecciona solo posiciones de cabeza. CH > 0 significa que Var
% necesita soporte en el cuerpo.
cv_head(Var, C):- C = #count{Pos : var_pos(Var,Pos), Pos <= VHI}, var(Var), last_index_var_in_head(VHI).

% Constraint de seguridad para stubs complejos.
% Si Var aparece en la cabeza (CH > 0) y no tiene ninguna aparicion segura en el
% cuerpo (cv_body = 0), se descarta la asignacion. Apariciones solo en agregados,
% aritmetica o comparaciones no bastan para ligar la variable de cabeza.
:- cv_head(Var,CH), cv_body(Var,0), CH > 0.
