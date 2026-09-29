% Comparison operator < against a fixed term.
% expect: target(V0) :- n(V0),V0<2.
#maxv(1). #maxbl(2). #maxhl(1). #maxpl(1).
#modeh(1,target(var(num,input))).
#modeb(1,n(var(num,output))).
#modeb(1,var(num,input)<2).
n(1..3).
#pos({target(1)},{}).
#neg({target(3)},{}).
