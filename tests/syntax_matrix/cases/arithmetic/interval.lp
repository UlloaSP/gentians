% Interval assignment produces its variable.
% expect: target(V0) :- V0=1..3.
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(num,input))).
#modeb(1,var(num)=1..3).
#modeb(1,var(num)=1..4).
#pos({target(1),target(3)},{}).
#neg({target(4)},{}).
