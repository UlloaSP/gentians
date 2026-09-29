% Nested function and tuple terms with constants in the head.
% expect: target(box(V0,red),(V0,V0)) :- p(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#constant(colour,red). #constant(colour,blue).
#modeh(1,target(box(var(node,input,x),const(colour)),(var(node,input,x),var(node,input,x)))).
#modeb(1,p(var(node,output))).
p(a).
#pos({target(box(a,red),(a,a))},{}).
#neg({target(box(a,blue),(a,a))},{}).
