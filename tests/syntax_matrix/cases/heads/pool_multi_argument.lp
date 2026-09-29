% Head pool varying several arguments at once.
% expect: p(1,2;3,4).
#maxv(0). #maxbl(0). #maxhl(1). #maxpl(1).
#modeh(1,p(1,2;3,4)).
#modeh(1,p(1,4;3,2)).
#pos({p(1,2),p(3,4)},{}).
#neg({p(1,4)},{}).
