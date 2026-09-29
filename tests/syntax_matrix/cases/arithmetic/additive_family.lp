% Direction-implicit addition and subtraction compile into one family.
% expect: diff(V0,V1,V2) :- a(V0),b(V1),V0-V1=V2.
#maxv(3). #maxbl(3). #maxhl(1). #maxpl(1).
#modeh(1,diff(var(num,input),var(num,input),var(num,output))).
#modeb(1,a(var(num,output))).
#modeb(1,b(var(num,output))).
#modeb(1,var(num)+var(num)=var(num)).
#modeb(1,var(num)-var(num)=var(num)).
a(5). b(2).
#pos({diff(5,2,3)},{}).
#neg({diff(5,2,7)},{}).
