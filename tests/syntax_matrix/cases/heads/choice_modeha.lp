% Cardinality head combined from #modeha elements with constants.
% expect: 1{paint(V0,red);paint(V0,blue)}1 :- node(V0).
#maxv(1). #maxbl(1). #minhl(1). #maxhl(2). #maxpl(1).
#constant(colour,red). #constant(colour,blue).
#modeha(2,paint(var(node,input),const(colour))).
#modeb(1,node(var(node,output))).
node(a).
#pos({paint(a,red)},{paint(a,blue)}).
#pos({paint(a,blue)},{paint(a,red)}).
#neg({paint(a,red),paint(a,blue)},{}).
#neg({},{paint(a,red),paint(a,blue)}).
