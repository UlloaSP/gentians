% A default-negated head acts as a constraint on p and defines nothing.
% expect: not blocked(V0) :- safe(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,not blocked(var(node,input))).
#modeb(1,safe(var(node,output))).
#modeb(1,node(var(node,output))).
node(a). node(b). safe(a).
{blocked(X)} :- node(X).
#pos({blocked(b)},{}).
#neg({blocked(a)},{}).
