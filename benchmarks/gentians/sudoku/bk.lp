index(1..4).
value(1..4).
block(R,C,(R-1)/2*2+(C-1)/2+1) :- index(R), index(C).
same_block(R1,C1,R2,C2) :- block(R1,C1,B), block(R2,C2,B), (R1,C1) != (R2,C2).
