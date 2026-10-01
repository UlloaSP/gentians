% expect: word("a,b").
% Strings are one ground term even when they contain delimiters and escapes.
#maxv(0).
#maxbl(0).
#maxhl(1).
#maxpl(1).
#constant(word,"a,b").
#constant(word,"quote: \", parentheses ), slash \\").
#modeh(1,word(const(word))).
#pos({word("a,b")},{word("quote: \", parentheses ), slash \\")},{}).
#neg({word("quote: \", parentheses ), slash \\")},{},{}).
