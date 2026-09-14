% ILASP mode-bias translation of coloring.txt.
% No learned or Gentians-generated rules are included.

% Source: graph-coloring synthetic benchmark
% Task: Three-color graph coloring.

edge(1, 2).
edge(1, 3).
edge(2, 5).
edge(2, 6).
edge(3, 4).
edge(4, 5).
edge(5, 6).
node(1..6).
e(X,Y) :- edge(X,Y).
e(Y,X) :- edge(X,Y).
node(1..6).

#pos({red(1), blue(2), blue(3), red(4), green(5), red(6)}, {}).
#pos({red(1), blue(2), green(3), blue(4), green(5), red(6)}, {}).
#pos({red(1), blue(2), green(3), red(4), green(5), red(6)}, {}).
#pos({green(1), blue(2), red(3), blue(4), green(5), red(6)}, {}).
#pos({green(1), blue(2), blue(3), red(4), green(5), red(6)}, {}).
#pos({red(1), blue(2), green(3), blue(4), red(5), green(6)}, {}).

#neg({red(1), red(2)}, {}).
#neg({red(1), red(3)}, {}).
#neg({blue(1), blue(2)}, {}).
#neg({green(3), green(4)}, {}).


% ILASP generates its hypothesis space from this bias.
#maxv(3).
#modeha(1,red(var(node)),(positive)).
#modeha(1,green(var(node)),(positive)).
#modeha(1,blue(var(node)),(positive)).
#modeb(1,node(var(node)),(positive)).
#modeb(1,e(var(node),var(node)),(positive,anti_reflexive)).
#modeb(2,red(var(node)),(positive)).
#modeb(2,green(var(node)),(positive)).
#modeb(2,blue(var(node)),(positive)).
#minhl(3).
#maxhl(3).
