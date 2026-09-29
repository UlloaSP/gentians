% Arithmetic, intervals and functions in background.
% expect: target(V0) :- p(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,p(var(node,output))).
#modeb(1,node(var(node,output))).
node(a). node(b).
code(a,1). code(b,4).
low(1..2).
p(X) :- code(X,N), low(M), N = M*1.
#pos({target(a)},{}).
#neg({target(b)},{}).
