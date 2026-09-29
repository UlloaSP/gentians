% Generated #modec conditions, positive and default-negated, on a head whose
% local variable Clingo expands into a disjunction over unblocked successors.
% expect: pick(V1):edge(V0,V1),not blocked(V1) :- start(V0).
#maxv(2). #maxbl(3). #maxhl(1). #maxpl(1).
#modeh(1,pick(var(node,any))).
#modeb(1,start(var(node,output))).
#modec(1,edge(var(node,any),var(node,any))).
#modec(1,not blocked(var(node,any))).
start(a). edge(a,b). edge(a,c). edge(a,d). blocked(d).
#pos({pick(b)},{pick(c),pick(d)}).
#pos({pick(c)},{pick(b),pick(d)}).
#neg({pick(d)},{}).
#neg({},{pick(b),pick(c)}).
