% Head element with an exact condition: Clingo reads it as a disjunction.
% expect: sel(V0):node(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,sel(var(node,any)):node(var(node,any))).
#modeh(1,sel(var(node,any)):other(var(node,any))).
node(a). node(b). other(c).
#pos({sel(a)},{sel(b),sel(c)}).
#pos({sel(b)},{sel(a),sel(c)}).
#neg({},{sel(a),sel(b)}).
