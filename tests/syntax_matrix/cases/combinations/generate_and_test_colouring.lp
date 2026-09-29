% Choice head with constants plus a learned constraint (generate and test).
% expect: 1{col(V0,red);col(V0,green)}1 :- node(V0).
% expect: :- edge(V0,V1),col(V0,V2),col(V1,V2).
#maxv(3). #maxbl(3). #maxhl(2). #maxpl(2).
#modeh(1,1{col(var(node,input,x),red);col(var(node,input,x),green)}1).
#modeh(1,{col(var(node,input,x),red);col(var(node,input,x),green)}).
#modeb(1,node(var(node,output))).
#modeb(1,edge(var(node,output),var(node,output))).
#modeb(2,col(var(node,input),var(colour,output))).
node(a). node(b). edge(a,b).
#pos({col(a,red),col(b,green)},{}).
#pos({col(a,green),col(b,red)},{}).
#neg({col(a,red),col(b,red)},{}).
#neg({col(a,green),col(b,green)},{}).
#neg({},{col(a,red),col(a,green)}).
