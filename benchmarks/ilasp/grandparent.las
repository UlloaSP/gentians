% ILASP mode-bias translation of grandparent.txt.
% No learned or Gentians-generated rules are included.

% Source: Metagol grandparent benchmark
% Task: Grandparent through parent helper predicate.

mother(i,a).
mother(c,f).
mother(c,g).
mother(f,h).
father(a,b).
father(a,c).
father(b,d).
father(b,e).

#pos({target(i,b)}, {}).
#pos({target(i,c)}, {}).
#pos({target(a,d)}, {}).
#pos({target(a,e)}, {}).
#pos({target(a,f)}, {}).
#pos({target(a,g)}, {}).
#pos({target(c,h)}, {}).

#neg({target(a,b)}, {}).
#neg({target(b,c)}, {}).
#neg({target(c,d)}, {}).
#neg({target(d,e)}, {}).
#neg({target(e,f)}, {}).
#neg({target(f,g)}, {}).
#neg({target(g,h)}, {}).
#neg({target(h,i)}, {}).


% ILASP generates its hypothesis space from this bias.
#maxv(3).
#modeh(1,target(var(person),var(person)),(positive)).
#modeh(1,target_1(var(person),var(person)),(positive)).
#modeb(1,father(var(person),var(person)),(positive,anti_reflexive)).
#modeb(1,mother(var(person),var(person)),(positive,anti_reflexive)).
#modeb(2,target_1(var(person),var(person)),(positive,anti_reflexive)).
