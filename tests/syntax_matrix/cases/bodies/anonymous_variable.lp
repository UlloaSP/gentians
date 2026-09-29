% expect: target(V0) :- edge(V0,_).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,edge(var(node,output),_)).
#modeb(1,edge(_,var(node,output))).
edge(a,b).
#pos({target(a)},{}).
#neg({target(b)},{}).
