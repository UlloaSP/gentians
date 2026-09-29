% #min head aggregate over weighted items.
% expect: #min{V0,V1:take(V1):item(V1,V0)}=2.
#maxv(2). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,#min{var(w,any,w),var(i,any,i):take(var(i,any,i)):item(var(i,any,i),var(w,any,w))}=2).
#modeh(1,#min{var(w,any,w),var(i,any,i):take(var(i,any,i)):item(var(i,any,i),var(w,any,w))}=1).
item(a,1). item(b,2). item(c,3).
#pos({take(b),take(c)},{take(a)}).
#pos({take(b)},{take(a),take(c)}).
#neg({take(a)},{}).
