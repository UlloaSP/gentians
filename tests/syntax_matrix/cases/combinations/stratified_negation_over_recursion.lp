% Recursive reachability consumed under default negation.
% expect: reach(V0) :- start(V0).
% expect: reach(V1) :- edge(V0,V1),reach(V0).
% expect: unreached(V0) :- node(V0),not reach(V0).
#maxv(2). #maxbl(2). #maxhl(1). #maxpl(3).
#modeh(1,reach(var(node,input))).
#modeh(1,unreached(var(node,input))).
#modeb(1,start(var(node,output))).
#modeb(1,node(var(node,output))).
#modeb(1,edge(var(node,input),var(node,output))).
#modeb(1,reach(var(node,output))).
#modeb(1,not reach(var(node,input))).
node(a). node(b). node(c). node(d).
start(a). edge(a,b). edge(b,c). edge(d,a).
#pos({unreached(d),reach(c)},{unreached(a),unreached(b),unreached(c)}).
#neg({unreached(c)},{}).
#neg({reach(d)},{}).
