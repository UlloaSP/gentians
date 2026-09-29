% Boolean constants as body literals.
% expect: p :- #true.
#maxv(0). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,p).
#modeb(1,#true).
#modeb(1,#false).
#pos({p},{}).
