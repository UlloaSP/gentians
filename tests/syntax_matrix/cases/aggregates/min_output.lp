% #min over a full tuple with an equality output.
% expect: total(V2) :- #min{V0,V1:item(V1,V0)}=V2.
#maxv(3). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,total(var(numeric,input))).
#modeb(1,#min{var(numeric,any,w),var(item,any,i):item(var(item,any,i),var(numeric,any,w))}=var(numeric,output)).
item(a,2). item(b,3).
#pos({total(2)},{}).
#neg({total(3)},{}).
