% expect: target(V0) :- -p(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,-p(var(node,output))).
#modeb(1,p(var(node,output))).
-p(a). p(b).
#pos({target(a)},{}).
#neg({target(b)},{}).
