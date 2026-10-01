% expect: -p((1;2),red).
% Strong negation and arity must survive pool factoring together.
#maxv(0).
#maxbl(0).
#maxhl(1).
#maxpl(1).
#modeh(1,-p(1,red;2,red)).
#pos({-p(1,red),-p(2,red)},{p(1,red),p(2,red),-p(1),-p(2)}).
