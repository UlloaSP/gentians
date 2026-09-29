% Classically negated head.
% expect: -ok(V0) :- bad(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,-ok(var(node,input))).
#modeh(1,ok(var(node,input))).
#modeb(1,bad(var(node,output))).
#modeb(1,good(var(node,output))).
bad(a). good(b).
#pos({-ok(a)},{ok(a)}).
#neg({-ok(b)},{}).
