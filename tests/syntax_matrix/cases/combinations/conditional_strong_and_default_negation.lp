% Conditional literal whose condition mixes an atom and default negation,
% concluding a strongly negated atom.
% expect: clean(V0) :- node(V0);-bad(V1):edge(V0,V1),not ignored(V1).
#maxv(2). #maxbl(4). #maxhl(1). #maxpl(1).
#modeh(1,clean(var(node,input))).
#modeb(1,node(var(node,output))).
#modeb(1,-bad(var(node,any,y)):edge(var(node,input),var(node,any,y))).
#modec(1,not ignored(var(node,any))).
node(a). node(b). node(c). node(d). node(e).
edge(a,b). edge(a,c). edge(b,c). edge(c,a). edge(d,e).
-bad(a). -bad(b). ignored(c).
#pos({clean(a),clean(b),clean(c),clean(e)},{}).
#neg({clean(d)},{}).
