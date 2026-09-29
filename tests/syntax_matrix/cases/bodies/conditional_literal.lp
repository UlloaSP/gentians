% Exact conditional literal in the body.
% expect: all_red :- red(V0):node(V0).
#maxv(1). #maxbl(2). #maxhl(1). #maxpl(1).
#modeh(1,all_red).
#modeb(1,red(var(node,any)):node(var(node,any))).
#modeb(1,red(var(node,any))).
node(a). node(b).
red(X) :- paint(X).
paint(z) :- #false.
#pos({all_red},{},{paint(a). paint(b).}).
#neg({all_red},{},{paint(a).}).
