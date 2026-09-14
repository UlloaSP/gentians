% ILASP mode-bias translation of clique.txt.
% No learned or Gentians-generated rules are included.

% Source: synthetic clique benchmark
% Task: Accept cliques of size 3.

v(1..9).
e(1,2).
e(1,5).
e(1,9).
e(3,1).
e(3,4).
e(3,8).
e(5,4).
e(6,3).
e(6,7).
e(2,5).
e(4,7).
e(7,1).
e(8,2).
e(9,5).
e(9,6).
3 {in(X) : v(X)} 3.
v(X) :- e(X,Y).
v(Y) :- e(X,Y).
ne(X,Y):- not e(X,Y), v(X), v(Y).

#pos({in(1), in(2), in(5)}, {}).
#pos({in(1), in(9), in(5)}, {}).

#neg({in(3)}, {}).
#neg({in(4)}, {}).

diff(A,B) :- v(A), v(B), A != B.
% ILASP generates its hypothesis space from this bias.
#maxv(2).
#modeb(2,v(var(node)),(positive)).
#modeb(2,ne(var(node),var(node)),(positive,anti_reflexive)).
#modeb(2,in(var(node)),(positive)).
#modeb(1,diff(var(node),var(node)),(positive,anti_reflexive)).
