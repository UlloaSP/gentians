% expect: target(V0) :- node(V0),not blocked(V0).
#maxv(1). #maxbl(2). #maxhl(1). #maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,node(var(node,output))).
#modeb(1,not blocked(var(node,input))).
node(a). node(b). blocked(b).
#pos({target(a)},{}).
#neg({target(b)},{}).
