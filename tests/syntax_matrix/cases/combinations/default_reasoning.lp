% Non-monotonic default with an exception defined by another learned clause.
% expect: flies(V0) :- bird(V0),not ab(V0).
% expect: ab(V0) :- penguin(V0).
#maxv(1). #maxbl(2). #maxhl(1). #maxpl(2).
#modeh(1,flies(var(animal,input))).
#modeh(1,ab(var(animal,input))).
#modeb(1,bird(var(animal,output))).
#modeb(1,penguin(var(animal,output))).
#modeb(1,not ab(var(animal,input))).
bird(tweety). bird(pingu). penguin(pingu).
#pos({flies(tweety)},{flies(pingu)}).
#neg({flies(pingu)},{}).
