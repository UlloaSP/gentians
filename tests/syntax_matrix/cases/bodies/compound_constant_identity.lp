% expect: target(V0) :- wrapped(V0,box((red,-2),nested("a,b"))).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#constant(word,box((red,-2),nested("a,b"))).
#modeh(1,target(var(node,input))).
#modeb(1,wrapped(var(node,output),const(word))).
#modeb(1,wrapped(var(node,output),box((red,-2),nested("a,b")))).
wrapped(a,box((red,-2),nested("a,b"))). wrapped(b,box(blue)).
#pos({target(a)},{}).
#neg({target(b)},{}).
