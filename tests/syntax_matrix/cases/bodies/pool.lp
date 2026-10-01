% Body pool stays one literal that expands to alternative bodies.
% expect: q :- p((1;2)).
#maxv(0). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,q).
#modeb(1,p(1;2)).
#modeb(1,p(3)).
p(X) :- s(X).
s(0) :- #false.
#pos({q},{},{s(2).}).
#neg({q},{},{s(3).}).
