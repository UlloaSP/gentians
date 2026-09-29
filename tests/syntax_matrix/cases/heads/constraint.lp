% Headless integrity constraint pruning a background choice.
% expect: :- p(V0),q(V0).
#maxv(1). #maxbl(2). #maxhl(0). #maxpl(1).
#modeb(1,p(var(node,output))).
#modeb(1,q(var(node,output))).
node(a).
{p(X);q(X)} :- node(X).
#pos({p(a)},{}).
#pos({q(a)},{}).
#neg({p(a),q(a)},{}).
