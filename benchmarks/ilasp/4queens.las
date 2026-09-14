% ILASP mode-bias translation of 4queens.txt.
% No learned or Gentians-generated rules are included.

% Source: http://www.hakank.org/answer_set_programming/nqueens.lp
% Task: 4-queens constraints.

#const n = 4.
number(1..n).
1 { q(X,Y) : number(Y) } 1 :- number(X).
1 { q(X,Y) : number(X) } 1 :- number(Y).

#pos({q(1,3), q(2,1), q(3,4), q(4,2)}, {}).
#pos({q(1,2), q(2,4), q(3,1), q(4,3)}, {}).

#neg({q(4,1), q(3,2), q(2,3), q(1,4)}, {}).
#neg({q(3,1), q(4,2), q(2,3), q(1,4)}, {}).
#neg({q(4,1), q(2,2), q(3,3), q(1,4)}, {}).
#neg({q(2,1), q(4,2), q(3,3), q(1,4)}, {}).
#neg({q(3,1), q(2,2), q(4,3), q(1,4)}, {}).
#neg({q(2,1), q(3,2), q(4,3), q(1,4)}, {}).
#neg({q(4,1), q(1,2), q(3,3), q(2,4)}, {}).
#neg({q(3,1), q(4,2), q(1,3), q(2,4)}, {}).
#neg({q(4,1), q(3,2), q(1,3), q(2,4)}, {}).
#neg({q(4,1), q(2,2), q(1,3), q(3,4)}, {}).
#neg({q(2,1), q(1,2), q(4,3), q(3,4)}, {}).
#neg({q(4,1), q(1,2), q(2,3), q(3,4)}, {}).
#neg({q(3,1), q(2,2), q(1,3), q(4,4)}, {}).
#neg({q(3,1), q(1,2), q(2,3), q(4,4)}, {}).
#neg({q(2,1), q(3,2), q(1,3), q(4,4)}, {}).
#neg({q(2,1), q(1,2), q(3,3), q(4,4)}, {}).
#neg({q(1,1), q(2,2), q(4,3), q(3,4)}, {}).
#neg({q(1,1), q(3,2), q(4,3), q(2,4)}, {}).
#neg({q(1,1), q(2,2), q(3,3), q(4,4)}, {}).
#neg({q(1,1), q(4,2), q(3,3), q(2,4)}, {}).
#neg({q(1,1), q(4,2), q(2,3), q(3,4)}, {}).
#neg({q(1,1), q(3,2), q(2,3), q(4,4)}, {}).

add(A,B,C) :- number(A), number(B), C = A + B.
sub(A,B,C) :- number(A), number(B), C = A - B.
lt(A,B) :- number(A), number(B), A < B.
% ILASP generates its hypothesis space from this bias.
#maxv(3).
#modeb(2,q(var(v),var(v)),(positive)).
#modeb(1,add(var(v),var(v),var(v)),(positive)).
#modeb(1,sub(var(v),var(v),var(v)),(positive)).
#modeb(1,lt(var(v),var(v)),(positive)).
