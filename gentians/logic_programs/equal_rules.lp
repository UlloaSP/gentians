% Reglas anti-duplicados para atomos repetidos en el mismo stub.
%
% Python detecta atomos textualmente iguales y emite hechos sameN/...
% Ejemplo para q(_____,_____), q(_____,_____):
%   same2(0,0,1).
%   same2(0,2,3).
% Ambos hechos tienen el mismo Id porque representan ocurrencias del mismo
% predicado/forma. Cada regla de abajo compara dos ocurrencias de igual aridad.
% Si todas sus posiciones reciben exactamente las mismas variables, se deriva
% equal. La constraint final ":- equal." descarta esa asignacion.
%
% Objetivo: evitar reglas con literales duplicados tras colocar variables, como
% q(V0,V1), q(V0,V1). Esos duplicados no cambian semantica y solo aumentan el
% espacio de busqueda.

% Caso aridad 1.
% same1(Id,P0) y same1(Id,P1) describen dos ocurrencias unarias del mismo
% atomo base. Si P0 y P1 son posiciones distintas pero ambas reciben la misma
% variable, las ocurrencias quedan identicas y se marca equal.
equal:-
    same1(Id,P0),
    same1(Id,P1),
    var_pos(V0,P0),
    var_pos(V1,P1),
    P0 != P1,
    V0 = V1.

% Caso aridad 2.
% Compara dos ocurrencias binarias del mismo Id. PA0/PA1 son las posiciones de
% la primera ocurrencia; PB0/PB1 las de la segunda. Solo hay duplicado si cada
% argumento coincide variable a variable: VA0 = VB0 y VA1 = VB1.
equal:-
    same2(Id,PA0,PA1),
    same2(Id,PB0,PB1),
    var_pos(VA0,PA0),
    var_pos(VA1,PA1),
    var_pos(VB0,PB0),
    var_pos(VB1,PB1),
    PA0 != PB0,
    PA1 != PB1,
    VA0 = VB0,
    VA1 = VB1.

% Caso aridad 3.
% Igual que aridad 2, pero exige coincidencia de los tres argumentos. Las
% desigualdades PAi != PBi evitan comparar una ocurrencia consigo misma.
equal:-
    same3(Id,PA0,PA1,PA2),
    same3(Id,PB0,PB1,PB2),
    var_pos(VA0,PA0),
    var_pos(VA1,PA1),
    var_pos(VA2,PA2),
    var_pos(VB0,PB0),
    var_pos(VB1,PB1),
    var_pos(VB2,PB2),
    PA0 != PB0,
    PA1 != PB1,
    PA2 != PB2,
    VA0 = VB0,
    VA1 = VB1,
    VA2 = VB2.

% Caso aridad 4.
% Deriva equal cuando dos atomos cuaternarios repetidos tienen la misma tupla
% completa de variables. Si cambia cualquier argumento, los literales no son
% identicos y la asignacion puede seguir.
equal:-
    same4(Id,PA0,PA1,PA2,PA3),
    same4(Id,PB0,PB1,PB2,PB3),
    var_pos(VA0,PA0),
    var_pos(VA1,PA1),
    var_pos(VA2,PA2),
    var_pos(VA3,PA3),
    var_pos(VB0,PB0),
    var_pos(VB1,PB1),
    var_pos(VB2,PB2),
    var_pos(VB3,PB3),
    PA0 != PB0,
    PA1 != PB1,
    PA2 != PB2,
    PA3 != PB3,
    VA0 = VB0,
    VA1 = VB1,
    VA2 = VB2,
    VA3 = VB3.

% Caso aridad 5.
% Misma comprobacion para predicados de cinco argumentos. El codigo solo cubre
% hasta aridad 5 porque get_same_atoms genera sameN segun la aridad detectada y
% el encoding necesita una regla concreta por cada N soportado.
equal:-
    same5(Id,PA0,PA1,PA2,PA3,PA4),
    same5(Id,PB0,PB1,PB2,PB3,PB4),
    var_pos(VA0,PA0),
    var_pos(VA1,PA1),
    var_pos(VA2,PA2),
    var_pos(VA3,PA3),
    var_pos(VA4,PA4),
    var_pos(VB0,PB0),
    var_pos(VB1,PB1),
    var_pos(VB2,PB2),
    var_pos(VB3,PB3),
    var_pos(VB4,PB4),
    PA0 != PB0,
    PA1 != PB1,
    PA2 != PB2,
    PA3 != PB3,
    PA4 != PB4,
    VA0 = VB0,
    VA1 = VB1,
    VA2 = VB2,
    VA3 = VB3,
    VA4 = VB4.

% Elimina toda solucion que haya producido dos literales identicos.
:- equal.
