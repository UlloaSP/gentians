% Disjunctions with omitted recalls keep the same semantics as recall *.
% expect: red(V0);green(V0) :- node(V0).
#maxv(1). #maxbl(1). #minhl(2). #maxhl(2). #maxpl(1).
#modehd(red(var(node,input))).
#modehd(green(var(node,input))).
#modeb(1,node(var(node,output))).
node(a).
#pos({red(a)},{green(a)}).
#pos({green(a)},{red(a)}).
#neg({},{red(a),green(a)}).
