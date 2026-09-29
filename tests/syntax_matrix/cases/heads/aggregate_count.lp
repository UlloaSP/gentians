% #count head aggregate with element conditions.
% expect: #count{V0:sel(V0):node(V0)}=1.
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,#count{var(node,any,x):sel(var(node,any,x)):node(var(node,any,x))}=1).
#modeh(1,{sel(var(node,any,x)):node(var(node,any,x))}).
node(a). node(b).
#pos({sel(a)},{sel(b)}).
#pos({sel(b)},{sel(a)}).
#neg({sel(a),sel(b)},{}).
#neg({},{sel(a),sel(b)}).
