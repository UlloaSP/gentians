#maxv(4).
#maxbl(3).
#maxhl(1).
#maxpl(6).
#modeb(1,hd(var(numeric,output))).
#modeb(1,#sum{var(numeric,any,value),var(index,any,position):d(var(index,any,position),var(numeric,any,value))}=var(numeric,output,result)).
#modeb(1,var(numeric)!=var(numeric)).
