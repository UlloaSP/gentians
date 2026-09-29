% Cardinality head element with default negation.
% expect: 1{not blocked;selected}1.
#maxv(0). #maxbl(0). #maxhl(2). #maxpl(1).
#modeh(1,1{not blocked;selected}1).
#modeh(1,selected).
{blocked}.
#pos({},{blocked,selected}).
#pos({blocked,selected},{}).
#neg({selected},{blocked}).
#neg({blocked},{selected}).
