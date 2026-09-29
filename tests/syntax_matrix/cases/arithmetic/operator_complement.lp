% Arithmetic term with operator complement assigning a head output.
% expect: f(V0,V1) :- n(V0),~V0=V1.
#maxv(2). #maxbl(2). #maxhl(1). #maxpl(1).
#modeh(1,f(var(num,input),var(num,output))).
#modeb(1,n(var(num,output))).
#modeb(1,~var(num,input)=var(num,output)).
n(1). n(2).
#pos({f(1,-2)},{}).
#pos({f(2,-3)},{}).
#neg({f(1,1)},{}).
