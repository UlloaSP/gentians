% Cardinality rule over conditional elements.
% expect: target(V0) :- p(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,p(var(node,output))).
#modeb(1,node(var(node,output))).
node(a). node(b).
1 {p(X):node(X)} 1.
#pos({target(a)},{target(b)}).
#neg({target(a),target(b)},{}).
