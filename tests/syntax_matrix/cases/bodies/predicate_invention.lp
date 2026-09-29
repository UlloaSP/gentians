% Invented helper predicate consumed by the target.
% expect: target(V0,V2) :- target_1(V0,V1),target_1(V1,V2).
% expect: target_1(V0,V1) :- mother(V0,V1).
% expect: target_1(V0,V1) :- father(V0,V1).
#maxv(3). #maxbl(2). #maxhl(1). #maxpl(3).
#modeh(1,target(var(person,input),var(person,output))).
#modeb(1,father(var(person,input),var(person,output))).
#modeb(1,mother(var(person,input),var(person,output))).
#invent(2,target_1(var(person,input),var(person,output))).
mother(i,a). mother(c,f). father(a,b). father(a,c). father(b,d).
#pos({target(i,b)},{}).
#pos({target(i,c)},{}).
#pos({target(a,d)},{}).
#pos({target(a,f)},{}).
#neg({target(a,b)},{}).
#neg({target(i,a)},{}).
#neg({target(b,d)},{}).
