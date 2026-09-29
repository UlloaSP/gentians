% Arithmetic term with operator bitwise_and assigning a head output.
% expect: f(V0,V1) :- n(V0),V0&3=V1.
#maxv(2). #maxbl(2). #maxhl(1). #maxpl(1).
#modeh(1,f(var(num,input),var(num,output))).
#modeb(1,n(var(num,output))).
#modeb(1,var(num,input)&3=var(num,output)).
n(5). n(6).
#pos({f(5,1)},{}).
#pos({f(6,2)},{}).
#neg({f(5,5)},{}).
