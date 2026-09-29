% Head #sum aggregate whose guard is bound by a body literal and whose
% elements carry comparison conditions.
% expect: #sum{V1,V2:take(V2):item(V2,V1),V1>1}=V0 :- cap(V0).
#maxv(3). #maxbl(3). #maxhl(1). #maxpl(1).
#modeh(1,#sum{var(numeric,any,w),var(item,any,i):take(var(item,any,i)):item(var(item,any,i),var(numeric,any,w)),var(numeric,any,w)>1}=var(numeric,input)).
#modeh(1,#sum{var(numeric,any,w),var(item,any,i):take(var(item,any,i)):item(var(item,any,i),var(numeric,any,w))}=var(numeric,input)).
#modeb(1,cap(var(numeric,output))).
item(a,1). item(b,2). item(c,3). cap(3).
#pos({take(c)},{take(a),take(b)}).
#neg({take(a),take(b)},{}).
