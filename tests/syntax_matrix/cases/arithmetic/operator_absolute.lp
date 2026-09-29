% Arithmetic term with operator absolute assigning a head output.
% expect: f(V0,V1) :- n(V0),|V0-3|=V1.
#maxv(2). #maxbl(2). #maxhl(1). #maxpl(1).
#modeh(1,f(var(num,input),var(num,output))).
#modeb(1,n(var(num,output))).
#modeb(1,|var(num,input)-3|=var(num,output)).
n(1). n(5).
#pos({f(1,2)},{}).
#pos({f(5,2)},{}).
#neg({f(1,-2)},{}).
