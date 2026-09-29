% Disjunctive head mixing strong negation with a default-negated body.
% expect: -ok(V0);flag(V0) :- node(V0),not safe(V0).
#maxv(1). #maxbl(2). #maxhl(2). #maxpl(1).
#modeh(1,-ok(var(node,input,x));flag(var(node,input,x))).
#modeh(1,-ok(var(node,input))).
#modeb(1,node(var(node,output))).
#modeb(1,not safe(var(node,input))).
node(a). node(b). safe(b).
#pos({-ok(a)},{flag(a)}).
#pos({flag(a)},{-ok(a)}).
#neg({-ok(b)},{}).
#neg({flag(b)},{}).
#neg({},{-ok(a),flag(a)}).
