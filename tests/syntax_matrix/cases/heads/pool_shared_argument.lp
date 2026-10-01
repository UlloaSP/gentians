% expect: p((1;2),red).
% A fact pool must keep both alternatives at arity two.
#maxv(0).
#maxbl(0).
#maxhl(1).
#maxpl(1).
#modeh(1,p(1,red;2,red)).
#pos({p(1,red),p(2,red)},{p(1),p(2)}).
