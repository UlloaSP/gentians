% ILASP mode-bias translation of even_odd.txt.
% No learned or Gentians-generated rules are included.

% Source: https://github.com/stassa/louise/blob/master/data/examples/even_odd.pl
% Task: Mutual recursion for even and odd numbers.

even(0).
prev(1,0).
prev(2,1).
prev(3,2).
prev(4,3).

#pos({odd(1), odd(3), even(2)}, {}).

#neg({even(3)}, {}).
#neg({even(1)}, {}).
#neg({odd(2)}, {}).


% ILASP generates its hypothesis space from this bias.
#maxv(3).
#modeh(1,even(var(v)),(positive)).
#modeh(1,odd(var(v)),(positive)).
#modeb(1,even(var(v)),(positive)).
#modeb(1,odd(var(v)),(positive)).
#modeb(2,prev(var(v),var(v)),(positive,anti_reflexive)).
