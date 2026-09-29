% Conditional literal in a background body.
% expect: target(V0) :- p(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,p(var(node,output))).
#modeb(1,node(var(node,output))).
node(a). node(b).
succ(a,b). ok(b).
p(X) :- node(X), ok(Y):succ(X,Y); succ(X,_).
#pos({target(a)},{}).
#neg({target(b)},{}).
