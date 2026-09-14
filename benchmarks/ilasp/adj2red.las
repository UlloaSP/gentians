% ILASP mode-bias translation of adjacent_to_red.txt.
% No learned or Gentians-generated rules are included.

% Source: https://github.com/metagol/metagol/blob/master/examples/adjacent-to-red.pl
% Task: Nodes adjacent to a red-colored node.

edge(a,b).
edge(b,a).
edge(c,d).
edge(c,e).
edge(d,e).
colour(a,red).
colour(b,green).
colour(c,red).
colour(d,red).
colour(e,green).
red(red).
green(green).

#pos({target(b)}, {}).
#pos({target(c)}, {}).

#neg({target(a)}, {}).
#neg({target(d)}, {}).
#neg({target(e)}, {}).


% ILASP generates its hypothesis space from this bias.
#maxv(3).
#modeh(1,target(var(node)),(positive)).
#modeb(1,edge(var(node),var(node)),(positive,anti_reflexive)).
#modeb(1,colour(var(node),var(colour)),(positive)).
#modeb(1,red(var(colour)),(positive)).
#modeb(1,green(var(colour)),(positive)).
#modeb(1,target(var(node)),(positive)).
