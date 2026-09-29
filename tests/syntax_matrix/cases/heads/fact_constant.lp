% Bodyless fact built from a #constant placeholder.
% expect: seed(a).
#maxv(0). #maxbl(0). #maxhl(1). #maxpl(1).
#constant(node,a). #constant(node,b).
#modeh(1,seed(const(node))).
#pos({seed(a)},{}).
#neg({seed(b)},{}).
