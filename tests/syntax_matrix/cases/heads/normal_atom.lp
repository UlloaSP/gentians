% Normal head with a positive body output.
% expect: target(V0) :- p(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,p(var(node,output))).
#modeb(1,q(var(node,output))).
p(a). p(b). q(c).
#pos({target(a),target(b)},{}).
#neg({target(c)},{}).
