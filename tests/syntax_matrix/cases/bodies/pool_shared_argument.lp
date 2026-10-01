% expect: q :- p((1;2),red).
% Both arity-two alternatives cover q; an arity-one context must not.
#maxv(0).
#maxbl(1).
#maxhl(1).
#maxpl(1).
#modeh(1,q).
#modeb(1,p(1,red;2,red)).
#pos({q},{},{p(1,red).}).
#pos({q},{},{p(2,red).}).
#neg({q},{},{p(1).}).
