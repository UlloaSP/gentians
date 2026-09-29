% Complete disjunctive head declared in #modeh.
% expect: red(V0);green(V0) :- node(V0).
#maxv(1). #maxbl(1). #maxhl(2). #maxpl(1).
#modeh(1,red(var(node,input,x));green(var(node,input,x))).
#modeh(1,red(var(node,input))).
#modeb(1,node(var(node,output))).
node(a).
#pos({red(a)},{green(a)}).
#pos({green(a)},{red(a)}).
#neg({},{red(a),green(a)}).
