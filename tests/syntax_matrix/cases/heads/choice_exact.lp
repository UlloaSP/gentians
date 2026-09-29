% Unbounded choice head.
% expect: {heads(V0);tails(V0)} :- coin(V0).
#maxv(1). #maxbl(1). #maxhl(2). #maxpl(1).
#modeh(1,{heads(var(coin,input,x));tails(var(coin,input,x))}).
#modeh(1,heads(var(coin,input))).
#modeb(1,coin(var(coin,output))).
coin(c).
#pos({heads(c)},{tails(c)}).
#pos({tails(c)},{heads(c)}).
#pos({heads(c),tails(c)},{}).
#pos({},{heads(c),tails(c)}).
