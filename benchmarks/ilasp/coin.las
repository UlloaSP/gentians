% ILASP mode-bias translation of coin.txt.
% No learned or Gentians-generated rules are included.

% Source: https://doc.ilasp.com/specification/cdpis.html
% Task: Choose heads or tails for each coin.

coin(c1).
coin(c2).
coin(c3).

#pos({heads(c1), tails(c2), heads(c3)}, {tails(c1), heads(c2), tails(c3)}).
#pos({heads(c1), heads(c2), tails(c3)}, {tails(c1), tails(c2), heads(c3)}).


% ILASP generates its hypothesis space from this bias.
#maxv(3).
#modeh(1,heads(var(coin))).
#modeh(1,tails(var(coin))).
#modeb(1,coin(var(coin)),(positive)).
#modeb(1,heads(var(coin))).
#modeb(1,tails(var(coin))).
