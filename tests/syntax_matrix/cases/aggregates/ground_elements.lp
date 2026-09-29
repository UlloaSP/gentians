% Aggregate with ground elements and no conditions.
% expect: ok :- 3=#sum{1;2}.
#maxv(0). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,ok).
#modeb(1,#sum{1;2}=3).
#pos({ok},{}).
