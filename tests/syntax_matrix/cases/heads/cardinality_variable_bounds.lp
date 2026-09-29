% Cardinality bounds bound by a body variable, conditional elements.
% expect: V0{sel(V1):node(V1)}V0 :- k(V0).
#maxv(2). #maxbl(2). #maxhl(1). #maxpl(1).
#modeh(1,var(num,input,n) {sel(var(node,any)):node(var(node,any))} var(num,input,n)).
#modeb(1,k(var(num,output))).
node(a). node(b). node(c). k(2).
#pos({sel(a),sel(b)},{sel(c)}).
#neg({sel(a),sel(b),sel(c)},{}).
#neg({sel(a)},{sel(b),sel(c)}).
