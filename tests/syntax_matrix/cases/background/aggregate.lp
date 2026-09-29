% Body aggregate with a comparison guard.
% expect: target(V0) :- p(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,p(var(node,output))).
#modeb(1,node(var(node,output))).
node(a). node(b).
edge(a,a). edge(a,b).
p(X) :- node(X), #count{Y:edge(X,Y)} >= 2.
#pos({target(a)},{}).
#neg({target(b)},{}).
