% Nested nonlinear expression compared against an absolute value.
% expect: target(V0) :- n(V0),(V0+1)*V0<=|V0-9|.
#maxv(1). #maxbl(2). #maxhl(1). #maxpl(1).
#modeh(1,target(var(num,input))).
#modeb(1,n(var(num,output))).
#modeb(1,(var(num,input)+1)*var(num,input)<=|var(num,input)-9|).
n(1..3).
#pos({target(1),target(2)},{}).
#neg({target(3)},{}).
