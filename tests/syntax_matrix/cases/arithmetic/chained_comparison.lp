% Chained comparison proven safe by Clingo produces its variable.
% expect: target(V0) :- 1<V0<4.
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,target(var(num,input))).
#modeb(1,1<var(num)<4).
#modeb(1,1<var(num)<5).
#pos({target(2),target(3)},{}).
#neg({target(4)},{}).
