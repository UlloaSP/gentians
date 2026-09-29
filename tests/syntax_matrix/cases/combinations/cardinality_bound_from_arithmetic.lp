% Choice bounds computed by a body arithmetic relation.
% expect: V1{sel(V2):node(V2)}V1 :- k(V0),V0+1=V1.
#maxv(3). #maxbl(3). #maxhl(1). #maxpl(1).
#modeh(1,var(numeric,input,n) {sel(var(node,any)):node(var(node,any))} var(numeric,input,n)).
#modeb(1,k(var(numeric,output))).
#modeb(1,var(numeric,input)+1=var(numeric,output)).
node(a). node(b). node(c). k(1).
#pos({sel(a),sel(b)},{sel(c)}).
#neg({sel(a)},{sel(b),sel(c)}).
#neg({sel(a),sel(b),sel(c)},{}).
