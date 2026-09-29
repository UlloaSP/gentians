% Pooled background fact provides p for closure.
% xfail: bug: clause_predicates extracts no head predicate from pooled heads such as p(a;c)
% expect: target(V0) :- p(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,p(var(node,output))).
#modeb(1,node(var(node,output))).
node(a). node(b).
p(a;c).
#pos({target(a)},{}).
#neg({target(b)},{}).
