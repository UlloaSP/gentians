% Aggregate element with a comparison condition.
% expect: big(V1) :- #count{V0:n(V0),V0>2}=V1.
#maxv(2). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,big(var(numeric,input))).
#modeb(1,#count{var(numeric,any,x):n(var(numeric,any,x)),var(numeric,any,x)>2}=var(numeric,output)).
n(1..4).
#pos({big(2)},{}).
#neg({big(4)},{}).
