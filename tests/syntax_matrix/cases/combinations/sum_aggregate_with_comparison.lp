% Grouped body #sum whose output feeds a comparison.
% expect: heavy(V0) :- group(V0),#sum{V1,V2:wg(V2,V0,V1)}=V3,V3>4.
#maxv(4). #maxbl(3). #maxhl(1). #maxpl(1).
#modeh(1,heavy(var(group,input))).
#modeb(1,group(var(group,output))).
#modeb(1,#sum{var(numeric,any,w),var(item,any,i):wg(var(item,any,i),var(group,any),var(numeric,any,w))}=var(numeric,output)).
#modeb(1,var(numeric,input)>4).
group(g1). group(g2).
wg(a,g1,3). wg(b,g1,3). wg(c,g2,3).
#pos({heavy(g1)},{}).
#neg({heavy(g2)},{}).
