% Bounded cardinality head.
% expect: 1{heads(V0);tails(V0)}1 :- coin(V0).
#maxv(1). #maxbl(1). #maxhl(2). #maxpl(1).
#modeh(1,1 {heads(var(coin,input,x));tails(var(coin,input,x))} 1).
#modeh(1,{heads(var(coin,input,x));tails(var(coin,input,x))}).
#modeb(1,coin(var(coin,output))).
coin(c).
#pos({heads(c)},{tails(c)}).
#pos({tails(c)},{heads(c)}).
#neg({heads(c),tails(c)},{}).
#neg({},{heads(c),tails(c)}).
