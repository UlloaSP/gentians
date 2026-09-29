% Example contexts with facts, rules, choices, disjunctions, aggregates and
% constraints; each context is isolated from the others.
% expect: target(V0) :- p(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,p(var(node,output))).
#modeb(1,node(var(node,output))).
node(a). node(b).
p(X) :- src(X).
src(z) :- #false.
#pos({target(a)},{},{src(a).}).
#pos({target(a)},{target(b)},{{src(X)} :- node(X). :- not src(a).}).
#pos({target(b)},{target(a)},{src(a);src(b). :- #count{X:src(X)} != 1.}).
#neg({target(a)},{},{}).
#neg({target(b)},{},{src(a).}).
