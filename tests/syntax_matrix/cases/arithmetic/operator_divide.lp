% Arithmetic term with operator divide assigning a head output.
% expect: f(V0,V1) :- n(V0),V0/2=V1.
#maxv(2). #maxbl(2). #maxhl(1). #maxpl(1).
#modeh(1,f(var(num,input),var(num,output))).
#modeb(1,n(var(num,output))).
#modeb(1,var(num,input)/2=var(num,output)).
n(4). n(5).
#pos({f(4,2)},{}).
#pos({f(5,2)},{}).
#neg({f(4,1)},{}).
