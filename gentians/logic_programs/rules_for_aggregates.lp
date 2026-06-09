% Reglas especificas para stubs con agregados ASP.
%
% Python emite, para cada agregado A:
% - aggregate_term_position(A,P): posiciones de la tupla antes de ":" dentro
%   del agregado, por ejemplo X,Y en #sum{X,Y : edge(X,Y)}.
% - aggregate_atom_position(A,P): posiciones de variables dentro del literal
%   que aparece despues de ":", por ejemplo X,Y en edge(X,Y).
% - aggregate_result_position(A,P): posicion del resultado a la derecha del
%   agregado, emitida desde Python aunque este archivo no la usa directamente.

% i) Todos los terminos de la tupla de un mismo agregado deben ser distintos.
% Si dos posiciones P0 y P1 de aggregate_term_position para el mismo agregado A
% reciben la misma variable, la asignacion se descarta. Esto evita tuplas como
% #sum{X,X : ...}, que reducen informacion y suelen ser simetrias inutiles.
:- var_pos(V0,P0), 
    var_pos(V1,P1), 
    P0 != P1, 
    aggregate_term_position(A,P0), 
    aggregate_term_position(A,P1),
    V0 = V1.


% ii) Registra que variable V aparece en la tupla de terminos del agregado A.
var_in_term_agg(A,V):- aggregate_term_position(A,VPos), var_pos(V,VPos).

% ii) Registra que variable V aparece en los atomos/literales internos del
% agregado A, es decir, en la parte despues de ":".
var_in_atom_agg(A,V):- aggregate_atom_position(A,VPos), var_pos(V,VPos).

% ii) Todo termino de la tupla debe aparecer tambien dentro del literal del
% mismo agregado. Elimina formas inseguras como #count{X : a(Y)}, donde X se
% cuenta/proyecta pero no esta ligado por el literal interno.
:- var_in_term_agg(A,V), not var_in_atom_agg(A,V).


% iii) Marca cualquier posicion que pertenece internamente a un agregado,
% tanto en la tupla antes de ":" como en el literal despues de ":".
aggregate_in_position(Pos):-
    aggregate_term_position(_,Pos).
aggregate_in_position(Pos):-
    aggregate_atom_position(_,Pos).

% iii) Detecta variables globales usadas en la tupla de un agregado.
% Una variable es global aqui si aparece como termino del agregado y tambien
% aparece fuera de cualquier posicion interna del agregado. Esa mezcla cambia
% el alcance de la variable: deja de ser local al elemento del agregado y pasa
% a depender del contexto exterior.
global_var_tuple(Var):- 
    var_pos(Var,Pos0),
    aggregate_term_position(_,Pos0),
    var_pos(Var,Pos1),
    not aggregate_in_position(Pos1),
    Pos0 != Pos1.

% Descarta cualquier asignacion donde un termino de tupla de agregado comparta
% variable con una posicion externa. Con esto, las variables de la tupla se
% mantienen locales al agregado y no se confunden con variables globales del
% resto de la regla.
:- global_var_tuple(_).
