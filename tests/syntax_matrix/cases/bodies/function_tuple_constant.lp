% expect: target(V0) :- wrapped(box(V0,red)).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#constant(colour,red). #constant(colour,blue).
#modeh(1,target(var(node,input))).
#modeb(1,wrapped(box(var(node,output),const(colour)))).
wrapped(box(a,red)). wrapped(box(b,blue)).
#pos({target(a)},{}).
#neg({target(b)},{}).
