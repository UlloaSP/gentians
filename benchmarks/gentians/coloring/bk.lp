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
