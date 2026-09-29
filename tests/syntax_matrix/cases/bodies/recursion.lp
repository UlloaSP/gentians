% Recursive definition through the learned head predicate.
% expect: path(V0,V1) :- edge(V0,V1).
% expect: path(V0,V2) :- edge(V0,V1),path(V1,V2).
#maxv(3). #maxbl(2). #maxhl(1). #maxpl(2).
#modeh(1,path(var(node,input),var(node,output))).
#modeb(1,edge(var(node,input),var(node,output))).
#modeb(1,path(var(node,input),var(node,output))).
edge(a,b). edge(b,c). edge(c,d).
#pos({path(a,b),path(a,c),path(a,d),path(b,d)},{}).
#neg({path(b,a)},{}).
#neg({path(d,a)},{}).
