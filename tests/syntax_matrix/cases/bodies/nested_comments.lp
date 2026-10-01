% expect: target(V0) :- base(V0).
%*%* #bias("ignored."). *%*%
%* outer
% this apparent terminator *% is inside a line comment
*%
base(a).
#maxv(1).
#maxbl(1).
#maxhl(1).
#maxpl(1).
#modeh(1,target(var(node,input))).
#modeb(1,base(var(node,output))).
#pos({target(a)},{target(b)},{}).
#neg({target(b)},{},{}).
