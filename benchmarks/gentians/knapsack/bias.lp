#maxv(4).
#maxbl(3).
#maxhl(1).
#maxpl(6).
#modeb(1,max_weight(var(numeric,output))).
#modeb(1,#sum{var(numeric,any,weight):el(var(numeric,any,value),var(numeric,any,weight))}=var(numeric,output,result)).
#modeb(1,var(numeric)>var(numeric)).
