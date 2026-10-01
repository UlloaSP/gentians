% Head pool stays one clause that grounds to several facts.
% expect: p((1;2)).
#maxv(0). #maxbl(0). #maxhl(1). #maxpl(1).
#modeh(1,p(1;2)).
#modeh(1,p(1;3)).
#pos({p(1),p(2)},{}).
#neg({p(3)},{}).
