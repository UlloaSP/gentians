% p/1 is defined only by an example context.
% expect: q :- p.
#maxv(0). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,q).
#modeb(1,p).
#pos({q},{},{p.}).
#neg({q},{},{}).
