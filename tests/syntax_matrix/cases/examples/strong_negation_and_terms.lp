% Classically negated and structured atoms inside examples.
% expect: -done(pair(V0,V0)) :- p(V0).
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,-done(pair(var(node,input,x),var(node,input,x)))).
#modeh(1,done(pair(var(node,input,x),var(node,input,x)))).
#modeb(1,p(var(node,output))).
#modeb(1,node(var(node,output))).
node(a). node(b). p(a).
#pos({-done(pair(a,a))},{done(pair(a,a))}).
#neg({-done(pair(b,b))},{}).
