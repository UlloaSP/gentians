% #sum head aggregate over weighted items.
% expect: #sum{V0,V1:take(V1):item(V1,V0)}=5.
#maxv(2). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,#sum{var(w,any,w),var(i,any,i):take(var(i,any,i)):item(var(i,any,i),var(w,any,w))}=5).
#modeh(1,#sum{var(w,any,w),var(i,any,i):take(var(i,any,i)):item(var(i,any,i),var(w,any,w))}=4).
item(a,2). item(b,3). item(c,5).
#pos({take(a),take(b)},{take(c)}).
#pos({take(c)},{take(a),take(b)}).
#neg({take(a)},{take(b),take(c)}).
