% #sum+ head aggregate over weighted items.
% expect: #sum+{V0,V1:take(V1):item(V1,V0)}=3.
#maxv(2). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,#sum+{var(w,any,w),var(i,any,i):take(var(i,any,i)):item(var(i,any,i),var(w,any,w))}=3).
#modeh(1,#sum+{var(w,any,w),var(i,any,i):take(var(i,any,i)):item(var(i,any,i),var(w,any,w))}=2).
item(a,1). item(b,2). item(c,3).
#pos({take(a),take(b)},{take(c)}).
#pos({take(c)},{take(a),take(b)}).
#neg({take(b)},{take(a),take(c)}).
