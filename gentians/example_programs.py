# Some examples
# https://github.com/metagol/metagol/tree/master/examples
# http://hakank.org/popper/
# https://users.dimi.uniud.it/~agostino.dovier/AIGAMES/DISPENSA.pdf

from .utils import print_error_and_exit
from .parser import Program, Example, ModeDeclaration

def coin_example() -> Program:
    '''
    # coin example
    # from https://doc.ilasp.com/specification/cdpis.html
    % Given:
    coin(c1). 
    coin(c2). 
    coin(c3).    
    % Learns:
    heads(V0):- coin(V0),not tails(V0).
    tails(V0):- coin(V0),not heads(V0).
    '''
    
    background : 'list[str]' = [
        'coin(c1).', 
        'coin(c2).', 
        'coin(c3).'
    ]
    
    # example structure: [Included,Excluded]
    # For positive examples, there should be at least
    # one answer set with all the Included and none of
    # the excluded
    positive_examples : 'list[Example]' = [
        Example(("heads(c1), tails(c2), heads(c3)", "tails(c1), heads(c2), tails(c3)"), True),
        Example(("heads(c1), heads(c2), tails(c3)", "tails(c1), tails(c2), heads(c3)"), True)
    ]

    negative_examples : 'list[Example]' = []

    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'heads', "1"), True),
        ModeDeclaration(("1", 'tails', "1"), True)
    ]

    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'coin', "1", "positive"), False),
        ModeDeclaration(("1", 'heads', "1", "negative"), False),
        ModeDeclaration(("1", 'tails', "1", "negative"), False)
    ]

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)

def even_odd_example() -> Program:
    '''
    # Goal
    even(V0):- odd(V1),prev(V0,V1).
    odd(V0):- even(V1),prev(V0,V1).
    '''
    # even odd example from
    # https://github.com/stassa/louise/blob/master/data/examples/even_odd.pl

    background : 'list[str]' = [
        'even(0).',
        "prev(1,0).",
        "prev(2,1).",
        "prev(3,2).",
        "prev(4,3)."
    ]
    
    positive_examples : 'list[Example]' = [
        Example(("odd(1), odd(3), even(2)", ""), True)
    ]

    negative_examples : 'list[Example]' = [
        Example(("even(3)", ""), False),
        Example(("even(1)", ""), False),
        Example(("odd(2)", ""), False)
    ]

    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'even', "1"), True),
        ModeDeclaration(("1", 'odd', "1"), True)
    ]
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'odd', "1", "positive"), False),
        ModeDeclaration(("2", 'prev', "2", "positive"), False)
    ]

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)
    

def animals_bird_example() -> Program:
    # from https://github.com/logic-and-learning-lab/Popper/tree/main/examples/animals_bird
    background : 'list[str]' = [
        "feathers(feathers).",
        "scales(scales).",
        "hair(hair).",
        "has_covering(dog,hair).",
        "has_covering(dolphin,none).",
        "has_covering(platypus,hair).",
        "has_covering(bat,hair).",
        "has_covering(trout,none).",
        "has_covering(herring,none).",
        "has_covering(shark,none).",
        "has_covering(eel,none).",
        "has_covering(lizard,scales).",
        "has_covering(crocodile,scales).",
        "has_covering(t_rex,scales).",
        "has_covering(snake,scales).",
        "has_covering(turtle,scales).",
        "has_covering(eagle,feathers).",
        "has_covering(ostrich,feathers).",
        "has_covering(penguin,feathers).",
        "has_milk(dog).",
        "has_milk(cat).",
        "has_milk(dolphin).",
        "has_milk(bat).",
        "has_milk(platypus).",
        "homeothermic(dog).",
        "homeothermic(cat).",
        "homeothermic(dolphin).",
        "homeothermic(platypus).",
        "homeothermic(bat).",
        "homeothermic(eagle).",
        "homeothermic(ostrich).",
        "homeothermic(penguin).",
        "has_eggs(platypus).",
        "has_eggs(trout).",
        "has_eggs(herring).",
        "has_eggs(shark).",
        "has_eggs(eel).",
        "has_eggs(lizard).",
        "has_eggs(crocodile).",
        "has_eggs(t_rex).",
        "has_eggs(snake).",
        "has_eggs(turtle).",
        "has_eggs(eagle).",
        "has_eggs(ostrich).",
        "has_eggs(penguin).",
        "has_gills(trout).",
        "has_gills(herring).",
        "has_gills(shark).",
        "has_gills(eel)."
    ]
    
    positive_examples : 'list[Example]' = [
        Example(("bird(eagle)", ""), True),
        Example(("bird(ostrich)", ""), True),
        Example(("bird(penguin)", ""), True)
    ]

    negative_examples : 'list[Example]' = [
        Example(("bird(dog)", ""), False),
        Example(("bird(dolphin)", ""), False),
        Example(("bird(platypus)", ""), False),
        Example(("bird(bat)", ""), False),
        Example(("bird(trout)", ""), False),
        Example(("bird(herring)", ""), False),
        Example(("bird(shark)", ""), False),
        Example(("bird(eel)", ""), False),
        Example(("bird(lizard)", ""), False),
        Example(("bird(crocodile)", ""), False),
        Example(("bird(t_rex)", ""), False),
        Example(("bird(snake)", ""), False),
        Example(("bird(turtle)", ""), False)
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'bird', "1"), True)
    ]

    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'feathers', "1", "positive"), False),
        ModeDeclaration(("1", 'scales', "1", "positive"), False),
        ModeDeclaration(("1", 'hair', "1", "positive"), False),
        ModeDeclaration(("2", 'has_covering', "2", "positive"), False),
        ModeDeclaration(("1", 'has_milk', "1", "positive"), False),
        ModeDeclaration(("1", 'homeothermic', "1", "positive"), False),
        ModeDeclaration(("1", 'has_eggs', "1", "positive"), False),
        ModeDeclaration(("1", 'has_gills', "1", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)

def coloring_example() -> Program:
    '''
    # Original program
    red(X) ; green(X) ; blue(X) :- node(X).
    e(X,Y) :- edge(X,Y).
    e(Y,X) :- edge(Y,X).

    node(1..6).

    edge(1, 2).
    edge(1, 3).
    edge(2, 5).
    edge(2, 6).
    edge(3, 4).
    edge(4, 5).
    edge(5, 6).

    #show red/1.
    #show green/1.
    #show blue/1.
    
    # TO LEARN
    red(X) ; green(X) ; blue(X) :- node(X).
    :- e(X,Y), red(X), red(Y).
    :- e(X,Y), green(X), green(Y).
    :- e(X,Y), blue(X), blue(Y).
    '''
    background : 'list[str]' = [
        "edge(1, 2).",
        "edge(1, 3).",
        "edge(2, 5).",
        "edge(2, 6).",
        "edge(3, 4).",
        "edge(4, 5).",
        "edge(5, 6).",
        "node(1..6).",
        "e(X,Y) :- edge(X,Y).",
        "e(Y,X) :- edge(Y,X).",
        "node(1..6)."
    ]
    
    # each string identifies a set of atoms that should be present in an AS.
    # ["odd(1) odd(3) even(2)"] means that it should exist at least one AS
    # where all the three are true..
    # If I have N positive examples, there should be at least one AS including each
    # example.

    positive_examples : list[Example] = [
        Example(("red(1), blue(2), blue(3), red(4), green(5), red(6)", ""), True),
        Example(("red(1), blue(2), green(3), blue(4), green(5), red(6)", ""), True),
        Example(("red(1), blue(2), green(3), red(4), green(5), red(6)", ""), True),
        Example(("green(1), blue(2), red(3), blue(4), green(5), red(6)", ""), True),
        Example(("green(1), blue(2), blue(3), red(4), green(5), red(6)", ""), True),
        Example(("red(1), blue(2), green(3), blue(4), red(5), green(6)", ""), True)
    ]

    # [ "even(3) even(1) odd(2)" ] states that there should not exist an AS
    # where all the three are true.
    negative_examples : list[Example] = [
        Example(("red(1), red(2)", ""), False),
        Example(("red(1), red(3)", ""), False),
        Example(("blue(1), blue(2)", ""), False),
        Example(("green(3), green(4)", ""), False)
    ]

    language_bias_head : list[ModeDeclaration] = [
        ModeDeclaration(("1", 'red', "1"), True),
        ModeDeclaration(("1", 'green', "1"), True),
        ModeDeclaration(("1", 'blue', "1"), True)
    ]

    language_bias_body : list[ModeDeclaration] = [
        ModeDeclaration(("1", 'node', "1", "positive"), False),
        ModeDeclaration(("1", 'edge', "2", "positive"), False),
        ModeDeclaration(("2", 'red', "1", "positive"), False),
        ModeDeclaration(("2", 'green', "1", "positive"), False),
        ModeDeclaration(("2", 'blue', "1", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def sudoku() -> Program:
    '''
    Sudoku example from ILASP.
    '''
    background : 'list[str]' = [
        "cell((1..4,1..4)).",
        "block((X, Y), tl) :- cell((X, Y)), X < 3, Y < 3.",
        "block((X, Y), tr) :- cell((X, Y)), X > 2, Y < 3.",
        "block((X, Y), bl) :- cell((X, Y)), X < 3, Y > 2.",
        "block((X, Y), br) :- cell((X, Y)), X > 2, Y > 2.",
        "same_row((X1,Y),(X2,Y)) :- X1 != X2, cell((X1,Y)), cell((X2, Y)).",
        "same_col((X,Y1),(X,Y2)) :- Y1 != Y2, cell((X,Y1)), cell((X, Y2)).",
        "same_block(C1,C2) :- block(C1, B), block(C2, B), C1 != C2.",
        "1 {value(V1,1);value(V1,2);value(V1,3);value(V1,4) } 1 :- same_block(V2,V1)."
    ]
    
    positive_examples : 'list[Example]' = [
        Example(("value((1,1),1), value((1,2),2), value((1,3),3), value((1,4),4), value((2,3),2)", "value((1,1),2), value((1,1),3), value((1,1),4)"), True)
    ]

    negative_examples : 'list[Example]' = [
        Example(("value((1,1),1), value((1,3),1)", ""), False),
        Example(("value((1,1),1), value((3,1),1)", ""), False),
        Example(("value((1,1),1), value((2,2),1)", ""), False)
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = []

    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("2", 'value', "2", "positive"), False),
        ModeDeclaration(("1", 'same_row', "2", "positive"), False),
        ModeDeclaration(("1", 'same_col', "2", "positive"), False),
        ModeDeclaration(("1", 'same_block', "2", "positive"), False)
    ]

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def euclid_example() -> Program:
    '''
    Models Euclid's algorithm.
    #const a=4.
    #const b=2.
    num(0..A) :- A = #max{a;b}.
    zero(0).
    one(1).
    pairprime(A,B) :- num(A), num(B), one(One), A > One, B > One, eucl(A,B,1).
    result(M) :- eucl(a,b,M).
    
    #show result/1.
    #show pairprime/2.
    

    # learn
    eucl(A,B,M) :- num(A), num(B), A < B, eucl(B,A,M).
    eucl(A,Z,A) :- zero(Z), num(A).
    eucl(A,B,M) :- num(A),num(B), zero(Z), A > B, B > Z, D = A \ B, eucl(B,D,M).
    '''
    # background knowledge
    background : 'list[str]' = [
        "#const a=4.",
        "#const b=2.",
        "num(0..A) :- A = #max{a;b}.",
        "zero(0).",
        "pairprime(A,B) :- num(A), num(B), A > 1, B > 1, eucl(A,B,1).",
        "result(M) :- eucl(a,b,M)."
    ]

    # positive examples
    positive_examples : 'list[Example]' = [
        Example(("pairprime(4,3), pairprime(3,2), pairprime(2,3), pairprime(3,4)", ""), True)
    ]
    negative_examples : 'list[Example]' = [
        Example(("pairprime(4,2)", ""), False),
        Example(("pairprime(2,4)", ""), False),
        Example(("pairprime(1,2)", ""), False),
        Example(("pairprime(2,1)", ""), False)
    ]

    # mode bias for the head
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "eucl", "3"), True)
    ]
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "euc", "3", "positive"), False),
        ModeDeclaration(("1", "zero", "1", "positive"), False),
        ModeDeclaration(("2", "num", "1", "positive"), False)
    ]

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)

def penguin_example() -> Program:
    '''
    % this requires constants so it cannot be currently solved.
    % Program.
    bird(a).
    bird(b).
    can(a, fly).
    can(b, swim).
    ability(fly).
    ability(swim).

    % penguin(X):- bird(X).
    % This is the solution
    % penguin(X):- bird(X), not can(X, fly).
    % penguin(X):- bird(X), not can(X, swim).
    % penguin(X):- bird(X), not can(X, fly), not can(X, swim).
    '''
    background : 'list[str]' = [
        "bird(a).",
        "bird(b).",
        "can(a, fly).",
        "can(b, swim).",
        "ability(fly).",
        "ability(swim)."
    ]

    positive_examples : 'list[Example]' = [
        Example(("penguin(b)", ""), True)
    ]

    negative_examples : 'list[Example]' = [
        Example(("penguin(a)", ""), False)
    ]

    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'penguin', "1"), True)
    ]

    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'bird', "1", "positive"), False),
        ModeDeclaration(("2", 'can', "2", "negative"), False),
        ModeDeclaration(("1", 'ability', "1", "positive"), False)
    ]

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def adjacent_to_red_example() -> Program:
    """
    from https://github.com/metagol/metagol/blob/master/examples/adjacent-to-red.pl
    goal target(A) :- edge(A,B),colour(B,C),red(C).
    """
    background : 'list[str]' = [
        "edge(a,b).",
        "edge(b,a).",
        "edge(c,d).",
        "edge(c,e).",
        "edge(d,e).",
        "colour(a,red).",
        "colour(b,green).",
        "colour(c,red).",
        "colour(d,red).",
        "colour(e,green).",
        "red(red).",
        "green(green)."
    ]
    
    positive_examples : 'list[Example]' = [
        Example(("target(b)", ""), True), 
        Example(("target(c)", ""), True)
    ]
    
    negative_examples : 'list[Example]' = [
        Example(("target(a)", ""), False), 
        Example(("target(d)", ""), False), 
        Example(("target(e)", ""), False),
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'target', "1"), True)
    ]

    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'edge', "2", "positive"), False),
        ModeDeclaration(("1", 'colour', "2", "positive"), False),
        ModeDeclaration(("1", 'red', "1", "positive"), False),
        ModeDeclaration(("1", 'green', "1", "positive"), False),
        ModeDeclaration(("1", 'target', "1", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def grandparent_example() -> Program:
    # from metagol
    '''
    % solution
    target(A,B):-target_1(A,C),target_1(C,B).
    target_1(A,B):-mother(A,B).
    target_1(A,B):-father(A,B).
    '''
    
    background : 'list[str]' = ["mother(i,a).", "mother(c,f).", "mother(c,g).", "mother(f,h).", "father(a,b).", "father(a,c).", "father(b,d).", "father(b,e)."]
    
    positive_examples : 'list[Example]' = [
        Example(("target(i,b), target(i,c), target(a,d), target(a,e), target(a,f), target(a,g), target(c,h)", ""), True)
    ]
    
    negative_examples : 'list[Example]' = [
        Example(("target(a,b)", ""), False), 
        Example(("target(b,c)", ""), False), 
        Example(("target(c,d)", ""), False), 
        Example(("target(d,e)", ""), False), 
        Example(("target(e,f)", ""), False), 
        Example(("target(f,g)", ""), False), 
        Example(("target(g,h)", ""), False), 
        Example(("target(h,i)", ""), False),
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'target', "2"), True),
        ModeDeclaration(("1", 'target_1', "2"), True)
    ]
    
    
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'father', "2", "positive"), False),
        ModeDeclaration(("1", 'mother', "2", "positive"), False),
        ModeDeclaration(("2", 'target_1', "2", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def subset_sum() -> Program:
    '''
    % Subset sum problem.
    {el(1)}.
    {el(2)}.
    {el(3)}.
    {el(4)}.
    {el(5)}.
    s(S):- S = #sum{X : el(X)}.
    :- s(S), S != 6.
    '''
    background : 'list[str]' = ["{el(1)}.", "{el(2)}.", "{el(3)}.", "{el(4)}.", "{el(5)}."]

    positive_examples : 'list[Example]' = [
        Example(("s(6)", ""), True)
    ]
    
    negative_examples : 'list[Example]' = []
    
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 's', "1"), True)
    ]
    
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'el', "1"), False)
    ]

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def subset_sum_double() -> Program:
    '''
    % Double subset sum problem.
    {el(1,2)}.
    {el(2,3)}.
    {el(3,5)}.
    {el(4,1)}.
    {el(5,9)}.
    
    % to learn
    s0(S):- S = #sum{X,Y : el(X,Y)}.
    s1(S):- S = #sum{Y,X : el(X,Y)}.
    ok(X):- s0(X), s1(X).
    #show ok/1.
    % results: ok(8). ok(9).
    '''
    background : 'list[str]' = [
        "{el(1,2)}.",
        "{el(2,3)}.",
        "{el(3,5)}.",
        "{el(4,1)}.",
        "{el(5,9)}."
    ]

    positive_examples : 'list[Example]' = [
        Example(("ok(0)", ""), True),
        Example(("ok(8)", ""), True),
        Example(("ok(9)", ""), True)
    ]

    negative_examples : 'list[Example]' = [
        Example(("ok(1)", ""), False),
        Example(("ok(2)", ""), False),
        Example(("ok(10)", ""), False)
    ]

    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'ok', "1"), True),
        ModeDeclaration(("1", 's0', "1"), True),
        ModeDeclaration(("1", 's1', "1"), True)
    ]

    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 's0', "1"), False),
        ModeDeclaration(("1", 's1', "1"), False)
    ]

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def subset_sum_double_and_sum() -> Program:
    '''
    % Double subset sum problem.
    {el(1,2)}.
    {el(2,3)}.
    {el(3,5)}.
    {el(4,1)}.
    {el(5,9)}.
    
    % to learn
    ok(S):- S0 = #sum{X,Y : el(X,Y)}, S0 = #sum{Y,X : el(X,Y)}, S = S0 + S0.
    #show ok/1.
    % results: ok(8). ok(9).
    '''
    background : 'list[str]' = [
        "{el(1,2)}.",
        "{el(2,3)}.",
        "{el(3,5)}.",
        "{el(4,1)}.",
        "{el(5,9)}."
    ]

    positive_examples : 'list[Example]' = [
        Example(("ok(0)", ""), True),
        Example(("ok(16)", ""), True),
        Example(("ok(18)", ""), True)
    ]

    negative_examples : 'list[Example]' = [
        Example(("ok(1)", ""), False),
        Example(("ok(2)", ""), False),
        Example(("ok(10)", ""), False)
    ]

    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'ok', "1"), True),
        ModeDeclaration(("1", 's0', "1"), True),
        ModeDeclaration(("1", 's1', "1"), True)
    ]

    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 's0', "1"), False),
        ModeDeclaration(("1", 's1', "1"), False)
    ]

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def subset_sum_double_and_prod():
    '''
    % Double subset sum problem.
    {el(1,2)}.
    {el(2,3)}.
    {el(3,5)}.
    {el(4,1)}.
    {el(5,9)}.
    
    % to learn
    s0(S0):- S0 = #sum{X,Y : el(X,Y)}.
    s1(S1):- S1 = #sum{Y,X : el(X,Y)}.
    ok(P):- s0(S0), s1(S1), P = S0 * S1.
    '''
    background : 'list[str]' = [
        "{el(1,2)}.",
        "{el(2,3)}.",
        "{el(3,5)}.",
        "{el(4,1)}.",
        "{el(5,9)}."
    ]

    positive_examples : 'list[Example]' = [
        Example(("ok(209)", ""), True),
        Example(("ok(144)", ""), True),
        Example(("ok(170)", ""), True),
        Example(("ok(252)", ""), True),
        Example(("ok(221)", ""), True)
    ]

    negative_examples : 'list[Example]' = [
        Example(("ok(3)", ""), False), # this cuts both + and -
        Example(("ok(5)", ""), False),
        Example(("ok(17)", ""), False),
        Example(("ok(19)", ""), False),
        Example(("ok(13)", ""), False),
    ]

    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'ok', "1"), True)

    ]

    language_bias_body : 'list[ModeDeclaration]' = []

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def subset_sum_triple():
    '''
    Sum of the terms at each position.
    {el(1,2,3)}.
    {el(2,3,5)}.
    {el(3,5,1)}.
    {el(4,1,3)}.
    {el(5,9,4)}.
    ok(V0):- #sum{V1,V2,V3:el(V1,V2,V3)}=V0,#sum{V2,V1,V3:el(V1,V2,V3)}=V0,#sum{V3,V1,V2:el(V1,V2,V3)}=V0.
    '''
    background : 'list[str]' = [
        "{el(1,2,3)}.",
        "{el(2,3,5)}.",
        "{el(3,5,1)}.",
        "{el(4,1,3)}.",
        "{el(5,9,4)}."
    ]

    positive_examples : 'list[Example]' = [
        Example(("ok(0)", ""), True),
        # Example(("ok(8)", ""), True),
        Example(("ok(9)", ""), True)
    ]

    negative_examples : 'list[Example]' = [
        Example(("ok(1)", ""), False),
        Example(("ok(2)", ""), False),
        Example(("ok(10)", ""), False),
        Example(("ok(15)", ""), False)
    ]

    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", 'ok', "1"), True)
    ]

    language_bias_body : 'list[ModeDeclaration]' = []

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def knapsack(opt : bool = False):
    '''
    # knapsack: learn only the weight constraint.
    % e(value,weight).
    e(1,3).
    e(2,3).
    e(3,5).
    e(4,4).
    e(5,9).

    % at most 3 elements
    0{el(X,Y) : e(X,Y)}3.

    % max weight
    max_weight(10).

    % to learn
    :- max_weight(WMax), W = #sum{Y, X : el(X,Y)}, W > WMax.

    % if optimize, also learn
    :~ el(Val,Weight). [Weight@1, Weight, Val] # both Weight and Val to count duplicates
    :~ el(Val,Weight). [-Val@2, Val, Weight]
    '''
    background : 'list[str]' = [
        "e(1,3).",
        "e(2,3).",
        "e(3,5).",
        "e(4,4).",
        "e(5,9).",
        "0{el(X,Y) : e(X,Y)}3.",
        "max_weight(10)."
    ]

    positive_examples : 'list[Example]' = [
        Example(("el(2,3), el(3,5)", ""), True),
        Example(("el(1,3), el(2,3), el(4,4)", ""), True)
    ]

    negative_examples : 'list[Example]' = [
        Example(("el(1,3), el(3,5), el(4,4)", ""), False),
        Example(("el(1,3), el(5,9)", ""), False)
    ]

    language_bias_head : 'list[ModeDeclaration]' = [
        # ModeDeclaration(("1", "ok", "1"), True),
        # ModeDeclaration(("1", "s0", "1"), True),
        # ModeDeclaration(("1", "s1", "1"), True)
    ]

    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "max_weight", "1", "positive"), False),
    ]

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def hamming(target_distance : int, harder : bool):
    '''
    Hamming distance between two binary strings.
    Given:
    pos(0..2).
    num(0..1).
    hd(1). % target distance
    % with hd(0), the constraint :- V0!=V1,v0(V1,V2),v1(V0,V2). suffices
    1{v0(Val,Pos) : num(Val)}1 :- pos(Pos).
    1{v1(Val,Pos) : num(Val)}1 :- pos(Pos).
    % too slow if i add these two rules to learn
    Learn if harder:
    problem: if there are cyclic rules, the grounder loops
    so it is not possible to compute the coverage 
    d(Pos,X):- v0(V0,Pos), v1(V1,Pos), X = |V0 - V1|.
    :- Distance = #sum{X,P : d(P,X)}, hd(D), Distance != D.
    else only the constraint
    '''
    if not (target_distance in [0,1]):
        import sys
        sys.exit('Hamming requires distance 0 or 1')
    
    background : 'list[str]' = [
        "pos(0..2).",
        "num(0..1).",
        f"hd({target_distance}). % target distance",
        "1{v0(Val,Pos) : num(Val)}1 :- pos(Pos).",
        "1{v1(Val,Pos) : num(Val)}1 :- pos(Pos)."
    ]
    
    if not harder:
        background.append("d(Pos,X):- v0(V0,Pos), v1(V1,Pos), X = |V0 - V1|.")

    if target_distance == 1:
        # all the 24 solutions for hd(1)
        positive_examples : 'list[Example]' = [
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,1), v1(1,0), v1(1,2)",""), True),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,1), v1(1,0), v1(1,2)",""), True),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,1), v1(0,2), v1(1,0)",""), True),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,1), v1(0,2), v1(1,0)",""), True),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(1,0), v1(1,1), v1(1,2)",""), True),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,2), v1(1,0), v1(1,1)",""), True),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(1,0), v1(1,1), v1(1,2)",""), True),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,2), v1(1,0), v1(1,1)",""), True),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(1,0), v1(1,1), v1(1,2)",""), True),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,1), v1(1,0), v1(1,2)",""), True),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,2), v1(1,0), v1(1,1)",""), True),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,1), v1(0,2), v1(1,0)",""), True),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,0), v1(0,2), v1(1,1)",""), True),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,0), v1(0,1), v1(0,2)",""), True),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,0), v1(1,1), v1(1,2)",""), True),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,0), v1(0,2), v1(1,1)",""), True),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,0), v1(1,1), v1(1,2)",""), True),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,0), v1(0,1), v1(1,2)",""), True),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,0), v1(0,1), v1(1,2)",""), True),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,0), v1(0,1), v1(0,2)",""), True),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,0), v1(1,1), v1(1,2)",""), True),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,0), v1(0,1), v1(0,2)",""), True),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,0), v1(0,1), v1(1,2)",""), True),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,0), v1(0,2), v1(1,1)",""), True)
        ]
        # all the 64 - 24 = 40 solutions for hd(1)
        negative_examples : 'list[Example]' = [
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,0), v1(0,1), v1(0,2)",""), False)
        ]
    else:
        # all the 8 solutions for hd(0)
        positive_examples : 'list[Example]' = [
            Example(("v0(1,0), v1(1,0), v1(0,1), v0(0,1), v0(1,2), v1(1,2)",""), True),
            Example(("v0(1,0), v1(1,0), v1(0,1), v0(0,1), v1(0,2), v0(0,2)",""), True),
            Example(("v0(1,0), v1(1,0), v0(1,1), v1(1,1), v0(1,2), v1(1,2)",""), True),
            Example(("v0(1,0), v1(1,0), v0(1,1), v1(1,1), v1(0,2), v0(0,2)",""), True),
            Example(("v1(0,0), v0(0,0), v1(0,1), v0(0,1), v0(1,2), v1(1,2)",""), True),
            Example(("v1(0,0), v0(0,0), v0(1,1), v1(1,1), v0(1,2), v1(1,2)",""), True),
            Example(("v1(0,0), v0(0,0), v1(0,1), v0(0,1), v1(0,2), v0(0,2)",""), True),
            Example(("v1(0,0), v0(0,0), v0(1,1), v1(1,1), v1(0,2), v0(0,2)",""), True)
        ]
        # all the 64 - 8 = 56 solutions for hd(0)
        negative_examples : 'list[Example]' = [
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,2), v1(1,0), v1(1,1)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,1), v1(0,2), v1(1,0)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(1,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,1), v1(1,0), v1(1,2)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,0), v1(0,2), v1(1,1)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,0), v1(1,1), v1(1,2)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(1,2), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(1,0), v0(1,1), v0(1,2), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,1), v0(1,0), v0(1,2), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(1,1), v0(1,2), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(0,2), v0(1,0), v0(1,1), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,2), v0(1,1), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,0), v1(0,1), v1(0,2)",""), False),
            Example(("v0(0,1), v0(0,2), v0(1,0), v1(0,0), v1(0,1), v1(1,2)",""), False),
            Example(("v0(0,0), v0(0,1), v0(0,2), v1(0,0), v1(0,1), v1(1,2)",""), False)
        ]

    # d(Pos,X):- v0(V0,Pos), v1(V1,Pos), X = |V0 - V1|.
    # :- Distance = #sum{X,P : d(P,X)}, hd(D), Distance != D.

    language_bias_head : 'list[ModeDeclaration]' = [
    ]
    if harder:
        language_bias_head.append(ModeDeclaration(("1", "d", "2"), True))

    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "hd", "1", "positive"), False)
    ]
    if harder:
        language_bias_body.append(ModeDeclaration(("1", "v0", "2", "positive"), False))
        language_bias_body.append(ModeDeclaration(("1", "v1", "2", "positive"), False))

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)

def n_4queens():
    '''
    % from http://www.hakank.org/answer_set_programming/nqueens.lp
    #const n = 4.

    % domain
    number(1..n).

    % alldifferent
    1 { q(X,Y) : number(Y) } 1 :- number(X).
    1 { q(X,Y) : number(X) } 1 :- number(Y).

    % These rules should be learned
    :- q(V0,V1),q(V1,V0).
    :- V0+V2=V1,q(V2,V1),q(V1,V0).
    '''
    background : 'list[str]' = [
        "#const n = 4.", 
        "number(1..n).", 
        "1 { q(X,Y) : number(Y) } 1 :- number(X).", 
        "1 { q(X,Y) : number(X) } 1 :- number(Y)."
    ]
    
    # all the existing solutions
    positive_examples : 'list[Example]' = [
        Example(("q(1,3), q(2,1), q(3,4), q(4,2)", ""), True),
        Example(("q(1,2), q(2,4), q(3,1), q(4,3)", ""), True)
    ]
    
    # all the possible placements - all existing solutions
    negative_examples : 'list[Example]' = [
        Example(("q(4,1), q(3,2), q(2,3), q(1,4)",""), False),
        Example(("q(3,1), q(4,2), q(2,3), q(1,4)",""), False),
        Example(("q(4,1), q(2,2), q(3,3), q(1,4)",""), False),
        Example(("q(2,1), q(4,2), q(3,3), q(1,4)",""), False),
        Example(("q(3,1), q(2,2), q(4,3), q(1,4)",""), False),
        Example(("q(2,1), q(3,2), q(4,3), q(1,4)",""), False),
        Example(("q(4,1), q(1,2), q(3,3), q(2,4)",""), False),
        Example(("q(3,1), q(4,2), q(1,3), q(2,4)",""), False),
        Example(("q(4,1), q(3,2), q(1,3), q(2,4)",""), False),
        Example(("q(4,1), q(2,2), q(1,3), q(3,4)",""), False),
        Example(("q(2,1), q(1,2), q(4,3), q(3,4)",""), False),
        Example(("q(4,1), q(1,2), q(2,3), q(3,4)",""), False),
        Example(("q(3,1), q(2,2), q(1,3), q(4,4)",""), False),
        Example(("q(3,1), q(1,2), q(2,3), q(4,4)",""), False),
        Example(("q(2,1), q(3,2), q(1,3), q(4,4)",""), False),
        Example(("q(2,1), q(1,2), q(3,3), q(4,4)",""), False),
        Example(("q(1,1), q(2,2), q(4,3), q(3,4)",""), False),
        Example(("q(1,1), q(3,2), q(4,3), q(2,4)",""), False),
        Example(("q(1,1), q(2,2), q(3,3), q(4,4)",""), False),
        Example(("q(1,1), q(4,2), q(3,3), q(2,4)",""), False),
        Example(("q(1,1), q(4,2), q(2,3), q(3,4)",""), False),
        Example(("q(1,1), q(3,2), q(2,3), q(4,4)",""), False)
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = []
    
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "q", "2", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def n_5queens():
    '''
    % from http://www.hakank.org/answer_set_programming/nqueens.lp
    #const n = 5.

    % domain
    number(1..n).

    % alldifferent
    1 { q(X,Y) : number(Y) } 1 :- number(X).
    1 { q(X,Y) : number(X) } 1 :- number(Y).

    % remove conflicting answers: these rules should be learned
    :- q(X1,Y), q(X2,Y), X1 < X2.
    :- q(X1,Y1), q(X2,Y2), X1 < X2, Y1 + X1 = Z, Z = Y2 + X2.
    :- q(X1,Y1), q(X2,Y2), X1 < X2, Y1 - X1 = Z, Z = Y2 - X2.
    '''
    background : 'list[str]' = [
        "#const n = 5.", 
        "number(1..n).", 
        "1 { q(X,Y) : number(Y) } 1 :- number(X).", 
        "1 { q(X,Y) : number(X) } 1 :- number(Y)."
    ]
    
    # all existing solutions (10)
    positive_examples : 'list[Example]' = [
        Example(("q(1,3), q(2,1), q(3,4), q(4,2), q(5,5)",""), True),
        Example(("q(1,1), q(2,3), q(3,5), q(4,2), q(5,4)",""), True),
        Example(("q(2,3), q(3,1), q(4,4), q(5,2), q(1,5)",""), True),
        Example(("q(1,2), q(2,4), q(3,1), q(4,3), q(5,5)",""), True),
        Example(("q(1,1), q(2,4), q(3,2), q(4,5), q(5,3)",""), True),
        Example(("q(1,3), q(2,5), q(3,2), q(4,4), q(5,1)",""), True),
        Example(("q(2,2), q(1,4), q(3,5), q(4,3), q(5,1)",""), True),
        Example(("q(2,2), q(3,4), q(4,1), q(5,3), q(1,5)",""), True),
        Example(("q(1,4), q(2,1), q(3,3), q(4,5), q(5,2)",""), True),
        Example(("q(1,2), q(2,5), q(3,3), q(4,1), q(5,4)",""), True)
    ]
    
    # some random examples (35) among all the solutions - valid
    negative_examples : 'list[Example]' = [
        Example(("q(1,1), q(2,5), q(3,4), q(4,3), q(5,2)",""), False),
        Example(("q(1,1), q(2,2), q(3,5), q(4,4), q(5,3)",""), False),
        Example(("q(1,1), q(2,4), q(3,5), q(4,2), q(5,3)",""), False),
        Example(("q(1,1), q(2,3), q(3,5), q(4,4), q(5,2)",""), False),
        Example(("q(1,1), q(2,3), q(3,4), q(4,5), q(5,2)",""), False),
        Example(("q(1,1), q(2,4), q(3,3), q(4,2), q(5,5)",""), False),
        Example(("q(1,1), q(2,3), q(3,4), q(4,2), q(5,5)",""), False),
        Example(("q(1,1), q(2,4), q(3,2), q(4,3), q(5,5)",""), False),
        Example(("q(1,1), q(2,2), q(3,4), q(4,3), q(5,5)",""), False),
        Example(("q(1,1), q(2,3), q(3,2), q(4,4), q(5,5)",""), False),
        Example(("q(1,1), q(2,2), q(3,3), q(4,4), q(5,5)",""), False),
        Example(("q(1,3), q(2,4), q(3,1), q(4,5), q(5,2)",""), False),
        Example(("q(1,3), q(2,4), q(3,2), q(4,5), q(5,1)",""), False),
        Example(("q(1,2), q(2,3), q(3,1), q(4,5), q(5,4)",""), False),
        Example(("q(1,4), q(2,3), q(3,1), q(4,5), q(5,2)",""), False),
        Example(("q(1,4), q(2,3), q(3,2), q(4,5), q(5,1)",""), False),
        Example(("q(1,2), q(2,3), q(3,4), q(4,5), q(5,1)",""), False),
        Example(("q(1,3), q(2,2), q(3,4), q(4,1), q(5,5)",""), False),
        Example(("q(1,3), q(2,4), q(3,5), q(4,1), q(5,2)",""), False),
        Example(("q(1,2), q(2,1), q(3,5), q(4,3), q(5,4)",""), False),
        Example(("q(1,2), q(2,4), q(3,5), q(4,3), q(5,1)",""), False),
        Example(("q(1,2), q(2,4), q(3,5), q(4,1), q(5,3)",""), False),
        Example(("q(1,3), q(2,1), q(3,5), q(4,2), q(5,4)",""), False),
        Example(("q(1,3), q(2,4), q(3,5), q(4,2), q(5,1)",""), False),
        Example(("q(1,3), q(2,2), q(3,5), q(4,4), q(5,1)",""), False),
        Example(("q(1,5), q(2,3), q(3,2), q(4,4), q(5,1)",""), False),
        Example(("q(1,5), q(2,2), q(3,3), q(4,4), q(5,1)",""), False),
        Example(("q(1,5), q(2,1), q(3,3), q(4,4), q(5,2)",""), False),
        Example(("q(1,5), q(2,2), q(3,1), q(4,4), q(5,3)",""), False),
        Example(("q(1,5), q(2,1), q(3,2), q(4,4), q(5,3)",""), False),
        Example(("q(1,5), q(2,2), q(3,1), q(4,3), q(5,4)",""), False),
        Example(("q(1,5), q(2,3), q(3,1), q(4,2), q(5,4)",""), False),
        Example(("q(1,5), q(2,4), q(3,3), q(4,2), q(5,1)",""), False),
        Example(("q(1,5), q(2,4), q(3,3), q(4,1), q(5,2)",""), False),
        Example(("q(1,5), q(2,4), q(3,2), q(4,3), q(5,1)",""), False)
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = []
    
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("2", "q", "2", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def clique() -> Program:
    '''
    Clique ok size 3.
    Given:
    3 {in(X) : v(X)} 3.
    v(X) :- e(X,Y).
    v(Y) :- e(X,Y).
    Learn:
    :- in(X), in(Y), X!=Y, not e(X,Y), not e(Y,X).
    Only 2 solutions:
    in(1) in(2) in(5)
    in(1) in(9) in(5)
    '''
    background : 'list[str]' = [
        "v(1..9).",
        "e(1,2).",
        "e(1,5).",
        "e(1,9).",
        "e(3,1).",
        "e(3,4).",
        "e(3,8).",
        "e(5,4).",
        "e(6,3).",
        "e(6,7).",
        "e(2,5).",
        "e(4,7).",
        "e(7,1).",
        "e(8,2).",
        "e(9,5).",
        "e(9,6).",
        "3 {in(X) : v(X)} 3.",
        "v(X) :- e(X,Y).",
        "v(Y) :- e(X,Y).",
        "ne(X,Y):- not e(X,Y), v(X), v(Y)."
    ]

    positive_examples : 'list[Example]' = [
        Example(("in(1), in(2), in(5)", ""), True),
        Example(("in(1), in(9), in(5)", ""), True)
    ]

    negative_examples : 'list[Example]' = [
        Example(("in(3)", ""), False),
        Example(("in(4)", ""), False)
    ]

    language_bias_head : 'list[ModeDeclaration]' = []

    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("2", "v", "1", "positive"), False),
        ModeDeclaration(("2", "ne", "2", "positive"), False),
        ModeDeclaration(("2", "in", "1", "positive"), False)
    ]

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def magic_square_no_diag():
    '''
    With aggregates: limited to the sum of columns and row.
    Constraint: the sum of the elements in the rows and columns
    should be the same.
    Given
    #const n = 3.
    #const s = n*(n*n + 1) / 2.
    size(1..n).
    val(1..n*n).
    1 { x(Row, Col, N) : val(N) } 1 :- size(Row), size(Col).
    1 { x(Row, Col, N) : size(Row), size(Col) } 1 :- val(N).
    % To learn:
    sum_row(R,S):- S = #sum{V : x(R,C,V), size(C)}, size(R).
    sum_col(C,S):- S = #sum{V : x(R,C,V), size(R)}, size(C).
    :- sum_col(C0,SC0), sum_col(C1,SC1), C0 != C1, SC0 != SC1.
    :- sum_row(R0,SR0), sum_row(R1,SR1), R0 != R1, SR0 != SR1.
    '''
    # https://en.wikipedia.org/wiki/Magic_square
    background : 'list[str]' = [
        "#const n = 3.",
        "#const s = n*(n*n + 1) / 2.",
        "size(1..n).",
        "val(1..n*n).",
        "1 { x(Row, Col, N) : val(N) } 1 :- size(Row), size(Col).",
        "1 { x(Row, Col, N) : size(Row), size(Col) } 1 :- val(N)."
    ]
    
    # all the 72 solutions
    positive_examples : 'list[Example]' = [
        Example(("x(1,1,4), x(1,2,2), x(1,3,9), x(2,1,8), x(2,2,6), x(2,3,1), x(3,1,3), x(3,2,7), x(3,3,5)",""), True),
        Example(("x(1,1,3), x(1,2,7), x(1,3,5), x(2,1,8), x(2,2,6), x(2,3,1), x(3,1,4), x(3,2,2), x(3,3,9)",""), True),
        Example(("x(1,1,7), x(1,2,3), x(1,3,5), x(2,1,6), x(2,2,8), x(2,3,1), x(3,1,2), x(3,2,4), x(3,3,9)",""), True),
        Example(("x(1,1,2), x(1,2,4), x(1,3,9), x(2,1,6), x(2,2,8), x(2,3,1), x(3,1,7), x(3,2,3), x(3,3,5)",""), True),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,9), x(2,2,5), x(2,3,1), x(3,1,2), x(3,2,7), x(3,3,6)",""), True),
        Example(("x(1,1,2), x(1,2,7), x(1,3,6), x(2,1,9), x(2,2,5), x(2,3,1), x(3,1,4), x(3,2,3), x(3,3,8)",""), True),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,9), x(2,3,1), x(3,1,7), x(3,2,2), x(3,3,6)",""), True),
        Example(("x(1,1,7), x(1,2,2), x(1,3,6), x(2,1,5), x(2,2,9), x(2,3,1), x(3,1,3), x(3,2,4), x(3,3,8)",""), True),
        Example(("x(1,1,7), x(1,2,5), x(1,3,3), x(2,1,6), x(2,2,1), x(2,3,8), x(3,1,2), x(3,2,9), x(3,3,4)",""), True),
        Example(("x(1,1,7), x(1,2,6), x(1,3,2), x(2,1,5), x(2,2,1), x(2,3,9), x(3,1,3), x(3,2,8), x(3,3,4)",""), True),
        Example(("x(1,1,3), x(1,2,5), x(1,3,7), x(2,1,8), x(2,2,1), x(2,3,6), x(3,1,4), x(3,2,9), x(3,3,2)",""), True),
        Example(("x(1,1,2), x(1,2,6), x(1,3,7), x(2,1,9), x(2,2,1), x(2,3,5), x(3,1,4), x(3,2,8), x(3,3,3)",""), True),
        Example(("x(1,1,2), x(1,2,9), x(1,3,4), x(2,1,6), x(2,2,1), x(2,3,8), x(3,1,7), x(3,2,5), x(3,3,3)",""), True),
        Example(("x(1,1,4), x(1,2,9), x(1,3,2), x(2,1,8), x(2,2,1), x(2,3,6), x(3,1,3), x(3,2,5), x(3,3,7)",""), True),
        Example(("x(1,1,3), x(1,2,8), x(1,3,4), x(2,1,5), x(2,2,1), x(2,3,9), x(3,1,7), x(3,2,6), x(3,3,2)",""), True),
        Example(("x(1,1,4), x(1,2,8), x(1,3,3), x(2,1,9), x(2,2,1), x(2,3,5), x(3,1,2), x(3,2,6), x(3,3,7)",""), True),
        Example(("x(1,1,5), x(1,2,1), x(1,3,9), x(2,1,3), x(2,2,8), x(2,3,4), x(3,1,7), x(3,2,6), x(3,3,2)",""), True),
        Example(("x(1,1,7), x(1,2,6), x(1,3,2), x(2,1,3), x(2,2,8), x(2,3,4), x(3,1,5), x(3,2,1), x(3,3,9)",""), True),
        Example(("x(1,1,3), x(1,2,8), x(1,3,4), x(2,1,7), x(2,2,6), x(2,3,2), x(3,1,5), x(3,2,1), x(3,3,9)",""), True),
        Example(("x(1,1,5), x(1,2,1), x(1,3,9), x(2,1,7), x(2,2,6), x(2,3,2), x(3,1,3), x(3,2,8), x(3,3,4)",""), True),
        Example(("x(1,1,7), x(1,2,3), x(1,3,5), x(2,1,2), x(2,2,4), x(2,3,9), x(3,1,6), x(3,2,8), x(3,3,1)",""), True),
        Example(("x(1,1,2), x(1,2,4), x(1,3,9), x(2,1,7), x(2,2,3), x(2,3,5), x(3,1,6), x(3,2,8), x(3,3,1)",""), True),
        Example(("x(1,1,6), x(1,2,8), x(1,3,1), x(2,1,7), x(2,2,3), x(2,3,5), x(3,1,2), x(3,2,4), x(3,3,9)",""), True),
        Example(("x(1,1,6), x(1,2,8), x(1,3,1), x(2,1,2), x(2,2,4), x(2,3,9), x(3,1,7), x(3,2,3), x(3,3,5)",""), True),
        Example(("x(1,1,9), x(1,2,1), x(1,3,5), x(2,1,2), x(2,2,6), x(2,3,7), x(3,1,4), x(3,2,8), x(3,3,3)",""), True),
        Example(("x(1,1,4), x(1,2,8), x(1,3,3), x(2,1,2), x(2,2,6), x(2,3,7), x(3,1,9), x(3,2,1), x(3,3,5)",""), True),
        Example(("x(1,1,2), x(1,2,6), x(1,3,7), x(2,1,4), x(2,2,8), x(2,3,3), x(3,1,9), x(3,2,1), x(3,3,5)",""), True),
        Example(("x(1,1,9), x(1,2,1), x(1,3,5), x(2,1,4), x(2,2,8), x(2,3,3), x(3,1,2), x(3,2,6), x(3,3,7)",""), True),
        Example(("x(1,1,9), x(1,2,4), x(1,3,2), x(2,1,5), x(2,2,3), x(2,3,7), x(3,1,1), x(3,2,8), x(3,3,6)",""), True),
        Example(("x(1,1,1), x(1,2,8), x(1,3,6), x(2,1,5), x(2,2,3), x(2,3,7), x(3,1,9), x(3,2,4), x(3,3,2)",""), True),
        Example(("x(1,1,5), x(1,2,3), x(1,3,7), x(2,1,9), x(2,2,4), x(2,3,2), x(3,1,1), x(3,2,8), x(3,3,6)",""), True),
        Example(("x(1,1,1), x(1,2,8), x(1,3,6), x(2,1,9), x(2,2,4), x(2,3,2), x(3,1,5), x(3,2,3), x(3,3,7)",""), True),
        Example(("x(1,1,5), x(1,2,3), x(1,3,7), x(2,1,1), x(2,2,8), x(2,3,6), x(3,1,9), x(3,2,4), x(3,3,2)",""), True),
        Example(("x(1,1,9), x(1,2,4), x(1,3,2), x(2,1,1), x(2,2,8), x(2,3,6), x(3,1,5), x(3,2,3), x(3,3,7)",""), True),
        Example(("x(1,1,8), x(1,2,1), x(1,3,6), x(2,1,3), x(2,2,5), x(2,3,7), x(3,1,4), x(3,2,9), x(3,3,2)",""), True),
        Example(("x(1,1,4), x(1,2,9), x(1,3,2), x(2,1,3), x(2,2,5), x(2,3,7), x(3,1,8), x(3,2,1), x(3,3,6)",""), True),
        Example(("x(1,1,3), x(1,2,5), x(1,3,7), x(2,1,4), x(2,2,9), x(2,3,2), x(3,1,8), x(3,2,1), x(3,3,6)",""), True),
        Example(("x(1,1,8), x(1,2,1), x(1,3,6), x(2,1,4), x(2,2,9), x(2,3,2), x(3,1,3), x(3,2,5), x(3,3,7)",""), True),
        Example(("x(1,1,1), x(1,2,9), x(1,3,5), x(2,1,8), x(2,2,4), x(2,3,3), x(3,1,6), x(3,2,2), x(3,3,7)",""), True),
        Example(("x(1,1,1), x(1,2,9), x(1,3,5), x(2,1,6), x(2,2,2), x(2,3,7), x(3,1,8), x(3,2,4), x(3,3,3)",""), True),
        Example(("x(1,1,6), x(1,2,2), x(1,3,7), x(2,1,1), x(2,2,9), x(2,3,5), x(3,1,8), x(3,2,4), x(3,3,3)",""), True),
        Example(("x(1,1,8), x(1,2,4), x(1,3,3), x(2,1,6), x(2,2,2), x(2,3,7), x(3,1,1), x(3,2,9), x(3,3,5)",""), True),
        Example(("x(1,1,6), x(1,2,2), x(1,3,7), x(2,1,8), x(2,2,4), x(2,3,3), x(3,1,1), x(3,2,9), x(3,3,5)",""), True),
        Example(("x(1,1,8), x(1,2,4), x(1,3,3), x(2,1,1), x(2,2,9), x(2,3,5), x(3,1,6), x(3,2,2), x(3,3,7)",""), True),
        Example(("x(1,1,3), x(1,2,7), x(1,3,5), x(2,1,4), x(2,2,2), x(2,3,9), x(3,1,8), x(3,2,6), x(3,3,1)",""), True),
        Example(("x(1,1,8), x(1,2,6), x(1,3,1), x(2,1,4), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,7), x(3,3,5)",""), True),
        Example(("x(1,1,8), x(1,2,6), x(1,3,1), x(2,1,3), x(2,2,7), x(2,3,5), x(3,1,4), x(3,2,2), x(3,3,9)",""), True),
        Example(("x(1,1,4), x(1,2,2), x(1,3,9), x(2,1,3), x(2,2,7), x(2,3,5), x(3,1,8), x(3,2,6), x(3,3,1)",""), True),
        Example(("x(1,1,5), x(1,2,7), x(1,3,3), x(2,1,1), x(2,2,6), x(2,3,8), x(3,1,9), x(3,2,2), x(3,3,4)",""), True),
        Example(("x(1,1,5), x(1,2,7), x(1,3,3), x(2,1,9), x(2,2,2), x(2,3,4), x(3,1,1), x(3,2,6), x(3,3,8)",""), True),
        Example(("x(1,1,9), x(1,2,2), x(1,3,4), x(2,1,1), x(2,2,6), x(2,3,8), x(3,1,5), x(3,2,7), x(3,3,3)",""), True),
        Example(("x(1,1,1), x(1,2,6), x(1,3,8), x(2,1,9), x(2,2,2), x(2,3,4), x(3,1,5), x(3,2,7), x(3,3,3)",""), True),
        Example(("x(1,1,1), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,7), x(2,3,3), x(3,1,9), x(3,2,2), x(3,3,4)",""), True),
        Example(("x(1,1,9), x(1,2,2), x(1,3,4), x(2,1,5), x(2,2,7), x(2,3,3), x(3,1,1), x(3,2,6), x(3,3,8)",""), True),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,2), x(2,2,7), x(2,3,6), x(3,1,9), x(3,2,5), x(3,3,1)",""), True),
        Example(("x(1,1,9), x(1,2,5), x(1,3,1), x(2,1,2), x(2,2,7), x(2,3,6), x(3,1,4), x(3,2,3), x(3,3,8)",""), True),
        Example(("x(1,1,2), x(1,2,7), x(1,3,6), x(2,1,4), x(2,2,3), x(2,3,8), x(3,1,9), x(3,2,5), x(3,3,1)",""), True),
        Example(("x(1,1,9), x(1,2,5), x(1,3,1), x(2,1,4), x(2,2,3), x(2,3,8), x(3,1,2), x(3,2,7), x(3,3,6)",""), True),
        Example(("x(1,1,1), x(1,2,5), x(1,3,9), x(2,1,8), x(2,2,3), x(2,3,4), x(3,1,6), x(3,2,7), x(3,3,2)",""), True),
        Example(("x(1,1,6), x(1,2,7), x(1,3,2), x(2,1,8), x(2,2,3), x(2,3,4), x(3,1,1), x(3,2,5), x(3,3,9)",""), True),
        Example(("x(1,1,8), x(1,2,3), x(1,3,4), x(2,1,1), x(2,2,5), x(2,3,9), x(3,1,6), x(3,2,7), x(3,3,2)",""), True),
        Example(("x(1,1,1), x(1,2,5), x(1,3,9), x(2,1,6), x(2,2,7), x(2,3,2), x(3,1,8), x(3,2,3), x(3,3,4)",""), True),
        Example(("x(1,1,8), x(1,2,3), x(1,3,4), x(2,1,6), x(2,2,7), x(2,3,2), x(3,1,1), x(3,2,5), x(3,3,9)",""), True),
        Example(("x(1,1,6), x(1,2,7), x(1,3,2), x(2,1,1), x(2,2,5), x(2,3,9), x(3,1,8), x(3,2,3), x(3,3,4)",""), True),
        Example(("x(1,1,5), x(1,2,9), x(1,3,1), x(2,1,7), x(2,2,2), x(2,3,6), x(3,1,3), x(3,2,4), x(3,3,8)",""), True),
        Example(("x(1,1,5), x(1,2,9), x(1,3,1), x(2,1,3), x(2,2,4), x(2,3,8), x(3,1,7), x(3,2,2), x(3,3,6)",""), True),
        Example(("x(1,1,7), x(1,2,2), x(1,3,6), x(2,1,3), x(2,2,4), x(2,3,8), x(3,1,5), x(3,2,9), x(3,3,1)",""), True),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,6), x(3,1,5), x(3,2,9), x(3,3,1)",""), True),
        Example(("x(1,1,6), x(1,2,1), x(1,3,8), x(2,1,7), x(2,2,5), x(2,3,3), x(3,1,2), x(3,2,9), x(3,3,4)",""), True),
        Example(("x(1,1,2), x(1,2,9), x(1,3,4), x(2,1,7), x(2,2,5), x(2,3,3), x(3,1,6), x(3,2,1), x(3,3,8)",""), True),
        Example(("x(1,1,7), x(1,2,5), x(1,3,3), x(2,1,2), x(2,2,9), x(2,3,4), x(3,1,6), x(3,2,1), x(3,3,8)",""), True),
        Example(("x(1,1,6), x(1,2,1), x(1,3,8), x(2,1,2), x(2,2,9), x(2,3,4), x(3,1,7), x(3,2,5), x(3,3,3)",""), True)
    ]
    
    # 200 not valid solutions
    negative_examples : 'list[Example]' = [
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,3), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,3), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,3), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,3), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,3), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,3), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,3), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,3), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,3), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,7), x(1,3,8), x(2,1,4), x(2,2,3), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,7), x(1,3,8), x(2,1,4), x(2,2,3), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,3), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,3), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,3), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,5), x(1,3,8), x(2,1,4), x(2,2,3), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,7), x(2,2,3), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,5), x(1,3,8), x(2,1,4), x(2,2,3), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,5), x(1,3,8), x(2,1,7), x(2,2,3), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,6), x(1,3,8), x(2,1,4), x(2,2,3), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,7), x(2,2,3), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,3), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,3), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,6), x(1,3,8), x(2,1,4), x(2,2,3), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,6), x(1,3,8), x(2,1,7), x(2,2,3), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,3), x(1,3,8), x(2,1,6), x(2,2,4), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,3), x(1,3,8), x(2,1,6), x(2,2,7), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,3), x(1,3,8), x(2,1,6), x(2,2,4), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,6), x(2,2,7), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,3), x(1,3,8), x(2,1,6), x(2,2,5), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,6), x(2,2,5), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,3), x(1,3,8), x(2,1,4), x(2,2,5), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,3), x(1,3,8), x(2,1,7), x(2,2,5), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,3), x(1,3,8), x(2,1,5), x(2,2,7), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,3), x(1,3,8), x(2,1,4), x(2,2,7), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,3), x(1,3,8), x(2,1,5), x(2,2,4), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,3), x(1,3,8), x(2,1,7), x(2,2,4), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,3), x(1,3,8), x(2,1,4), x(2,2,5), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,7), x(2,2,5), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,5), x(2,2,7), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,3), x(1,3,8), x(2,1,4), x(2,2,7), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,3), x(1,3,8), x(2,1,5), x(2,2,4), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,3), x(1,3,8), x(2,1,7), x(2,2,4), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,3), x(1,3,8), x(2,1,5), x(2,2,6), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,5), x(2,2,6), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,3), x(1,3,8), x(2,1,4), x(2,2,6), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,7), x(2,2,6), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,3), x(1,3,8), x(2,1,4), x(2,2,6), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,3), x(1,3,8), x(2,1,7), x(2,2,6), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,5), x(1,3,8), x(2,1,4), x(2,2,6), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,4), x(2,2,6), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,5), x(1,3,8), x(2,1,3), x(2,2,6), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,7), x(2,2,6), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,7), x(2,2,6), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,3), x(2,2,6), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,6), x(1,3,8), x(2,1,4), x(2,2,5), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,6), x(1,3,8), x(2,1,4), x(2,2,5), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,6), x(1,3,8), x(2,1,7), x(2,2,5), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,6), x(1,3,8), x(2,1,3), x(2,2,5), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,7), x(2,2,5), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,3), x(2,2,5), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,7), x(1,3,8), x(2,1,4), x(2,2,5), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,5), x(1,3,8), x(2,1,4), x(2,2,7), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,4), x(2,2,5), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,4), x(2,2,7), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,5), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,7), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,3), x(2,2,5), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,3), x(2,2,7), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,5), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,7), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,7), x(1,3,8), x(2,1,3), x(2,2,5), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,5), x(1,3,8), x(2,1,3), x(2,2,7), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,5), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,5), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,5), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,5), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,5), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,5), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,4), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,4), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,7), x(2,2,4), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,5), x(1,3,8), x(2,1,3), x(2,2,4), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,5), x(1,3,8), x(2,1,7), x(2,2,4), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,5), x(1,3,8), x(2,1,3), x(2,2,4), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,4), x(2,2,6), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,7), x(1,3,8), x(2,1,4), x(2,2,6), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,6), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,7), x(1,3,8), x(2,1,3), x(2,2,6), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,6), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,3), x(2,2,6), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,6), x(1,3,8), x(2,1,4), x(2,2,7), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,6), x(1,3,8), x(2,1,4), x(2,2,7), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,7), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,6), x(1,3,8), x(2,1,3), x(2,2,7), x(2,3,9), x(3,1,4), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,7), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,3), x(2,2,7), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,6), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,6), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,6), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,6), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,6), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,6), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,4), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,4), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,6), x(1,3,8), x(2,1,7), x(2,2,4), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,6), x(1,3,8), x(2,1,3), x(2,2,4), x(2,3,9), x(3,1,7), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,6), x(1,3,8), x(2,1,7), x(2,2,4), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,6), x(1,3,8), x(2,1,3), x(2,2,4), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,7), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,4), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,7), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,7), x(1,3,8), x(2,1,3), x(2,2,4), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,7), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,4), x(2,3,9), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,7), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,7), x(1,3,8), x(2,1,3), x(2,2,4), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,7), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,4), x(2,3,9), x(3,1,6), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,7), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,4), x(2,3,9), x(3,1,5), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,3), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,3), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,3), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,3), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,6), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,7), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,5), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,5), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,5), x(1,2,6), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,5), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,6), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,7), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,7), x(1,2,3), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,6), x(1,2,3), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,4), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,6), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,4), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,3), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,3), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,5), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,3), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,4), x(1,2,6), x(1,3,8), x(2,1,7), x(2,2,2), x(2,3,9), x(3,1,5), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,4), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,6), x(1,3,8), x(2,1,5), x(2,2,2), x(2,3,9), x(3,1,4), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,4), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,6), x(2,2,2), x(2,3,9), x(3,1,4), x(3,2,7), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,4), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,6), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,6), x(1,3,8), x(2,1,4), x(2,2,2), x(2,3,9), x(3,1,7), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,7), x(1,3,8), x(2,1,4), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,5), x(3,3,1)",""), False),
        Example(("x(1,1,3), x(1,2,5), x(1,3,8), x(2,1,4), x(2,2,2), x(2,3,9), x(3,1,6), x(3,2,7), x(3,3,1)",""), False)
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("2", "sum_row", "2"), True),
        ModeDeclaration(("2", "sum_col", "2"), True)
    ]
    
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "size", "1", "positive"), False),
        ModeDeclaration(("2", "sum_row", "2", "positive"), False),
        ModeDeclaration(("2", "sum_col", "2", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)
    

def set_partition_sum():
    '''
    Inspired by: http://www.hakank.org/answer_set_programming/set_partition.lp
    Set partition problem: given the set S = {1, 2, ..., n}, 
    find two sets A and B such that:
    - A U B = S
    - sum(A) = sum(B)
    -------------
    Given:
    #const n = 12. 
    val(1..n).
    partition(1..2).
    % split the numbers in two partitions
    1 { p(P, I) : partition(P) } 1 :- val(I).
    % symmetry breaking
    p(1,1).
    Learn:
    sum_partition(Sum,Partition):-
        partition(Partition),
        Sum = #sum{I : p(Partition,I)}.
    :- sum_partition(P0, S1), sum_partition(P1, S2), P0 != P1, S1 != S2.
    '''

    background : 'list[str]' = [
        "#const n = 12.",
        "val(1..n).",
        "partition(1..2).",
        "1 { p(P, I) : partition(P) } 1 :- val(I).",
        "p(1,1)."
    ]
    
    # 10 of the 62 existing solutions
    positive_examples : 'list[Example]' = [
        Example(("p(1,1), p(1,5), p(1,10), p(1,11), p(1,12), p(2,2), p(2,3), p(2,4), p(2,6), p(2,7), p(2,8), p(2,9)",""), True),
        Example(("p(1,1), p(1,4), p(1,5), p(1,8), p(1,10), p(1,11), p(2,2), p(2,3), p(2,6), p(2,7), p(2,9), p(2,12)",""), True),
        Example(("p(1,1), p(1,3), p(1,5), p(1,8), p(1,10), p(1,12), p(2,2), p(2,4), p(2,6), p(2,7), p(2,9), p(2,11)",""), True),
        Example(("p(1,1), p(1,3), p(1,4), p(1,8), p(1,11), p(1,12), p(2,2), p(2,5), p(2,6), p(2,7), p(2,9), p(2,10)",""), True),
        Example(("p(1,1), p(1,3), p(1,5), p(1,9), p(1,10), p(1,11), p(2,2), p(2,4), p(2,6), p(2,7), p(2,8), p(2,12)",""), True),
        Example(("p(1,1), p(1,3), p(1,4), p(1,9), p(1,10), p(1,12), p(2,2), p(2,5), p(2,6), p(2,7), p(2,8), p(2,11)",""), True),
        Example(("p(1,1), p(1,8), p(1,9), p(1,10), p(1,11), p(2,2), p(2,3), p(2,4), p(2,5), p(2,6), p(2,7), p(2,12)",""), True),
        Example(("p(1,1), p(1,4), p(1,5), p(1,8), p(1,9), p(1,12), p(2,2), p(2,3), p(2,6), p(2,7), p(2,10), p(2,11)",""), True),
        Example(("p(1,1), p(1,4), p(1,5), p(1,7), p(1,10), p(1,12), p(2,2), p(2,3), p(2,6), p(2,8), p(2,9), p(2,11)",""), True),
        Example(("p(1,1), p(1,7), p(1,9), p(1,10), p(1,12), p(2,2), p(2,3), p(2,4), p(2,5), p(2,6), p(2,8), p(2,11)",""), True)
    ]
    
    # some of the 62 possible placements
    negative_examples : 'list[Example]' = [
        Example(("p(1,1), p(1,4), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(1,12), p(2,2), p(2,3), p(2,5), p(2,10)",""), False),
        Example(("p(1,1), p(1,2), p(1,4), p(1,5), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(2,3), p(2,10), p(2,12)",""), False),
        Example(("p(1,1), p(1,4), p(1,5), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(2,2), p(2,3), p(2,10), p(2,12)",""), False),
        Example(("p(1,1), p(1,2), p(1,4), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(2,3), p(2,5), p(2,10), p(2,12)",""), False),
        Example(("p(1,1), p(1,4), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(2,2), p(2,3), p(2,5), p(2,10), p(2,12)",""), False),
        Example(("p(1,1), p(1,2), p(1,3), p(1,5), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(1,12), p(2,4), p(2,10)",""), False),
        Example(("p(1,1), p(1,2), p(1,5), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(1,12), p(2,3), p(2,4), p(2,10)",""), False),
        Example(("p(1,1), p(1,2), p(1,3), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(1,12), p(2,4), p(2,5), p(2,10)",""), False),
        Example(("p(1,1), p(1,2), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(1,12), p(2,3), p(2,4), p(2,5), p(2,10)",""), False),
        Example(("p(1,1), p(1,2), p(1,3), p(1,5), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(2,4), p(2,10), p(2,12)",""), False),
        Example(("p(1,1), p(1,2), p(1,3), p(1,6), p(1,7), p(1,8), p(1,9), p(1,11), p(2,4), p(2,5), p(2,10), p(2,12)",""), False),
        Example(("p(1,1), p(2,2), p(2,3), p(2,4), p(2,5), p(2,6), p(2,7), p(2,8), p(2,9), p(2,10), p(2,11), p(2,12)",""), False),
        Example(("p(1,1), p(1,3), p(1,4), p(1,5), p(1,6), p(1,7), p(1,8), p(1,9), p(1,10), p(1,11), p(1,12), p(2,2)",""), False)
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "sum_partition", "2"), True)
    ]
    
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("2", "sum_partition", "2", "positive"), False),
        ModeDeclaration(("1", "partition", "2", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def set_partition_sum_and_cardinality():
    '''
    Inspired by: http://www.hakank.org/answer_set_programming/set_partition.lp
    Set partition problem: given the set S = {1, 2, ..., n}, 
    find two sets A and B such that:
    - A U B = S
    - sum(A) = sum(B)
    - |A| = |B|
    -------------
    Given:
    #const n = 12. 
    val(1..n).
    partition(1..2).
    % split the numbers in two partitions
    1 { p(P, I) : partition(P) } 1 :- val(I).
    % symmetry breaking
    p(1,1).
    Learn:
    sum_partition(Sum,Partition):-
        partition(Partition),
        Sum = #sum{I : p(Partition,I)}.
    :- sum_partition(P0, S1), sum_partition(P1, S2), P0 != P1, S1 != S2.
    count_partition(Count,Partition):-
        partition(Partition),
        Count = #count{I : p(Partition,I)}.
    :- count_partition(P0, S1), count_partition(P1, S2), P0 != P1, S1 != S2.
    '''

    background : 'list[str]' = [
        "#const n = 12.",
        "val(1..n).",
        "partition(1..2).",
        "1 { p(P, I) : partition(P) } 1 :- val(I).",
        "p(1,1)."
    ]
    
    # all the 29 existing solutions
    positive_examples : 'list[Example]' = [
        Example(("p(1,1), p(1,4), p(1,5), p(1,8), p(1,9), p(1,12), p(2,2), p(2,3), p(2,6), p(2,7), p(2,10), p(2,11)",""), True),
        Example(("p(1,1), p(1,4), p(1,5), p(1,8), p(1,10), p(1,11), p(2,2), p(2,3), p(2,6), p(2,7), p(2,9), p(2,12)",""), True),
        Example(("p(1,1), p(1,3), p(1,5), p(1,9), p(1,10), p(1,11), p(2,2), p(2,4), p(2,6), p(2,7), p(2,8), p(2,12)",""), True),
        Example(("p(1,1), p(1,3), p(1,5), p(1,8), p(1,10), p(1,12), p(2,2), p(2,4), p(2,6), p(2,7), p(2,9), p(2,11)",""), True),
        Example(("p(1,1), p(1,4), p(1,5), p(1,7), p(1,10), p(1,12), p(2,2), p(2,3), p(2,6), p(2,8), p(2,9), p(2,11)",""), True),
        Example(("p(1,1), p(1,3), p(1,7), p(1,8), p(1,9), p(1,11), p(2,2), p(2,4), p(2,5), p(2,6), p(2,10), p(2,12)",""), True),
        Example(("p(1,1), p(1,5), p(1,6), p(1,7), p(1,9), p(1,11), p(2,2), p(2,3), p(2,4), p(2,8), p(2,10), p(2,12)",""), True),
        Example(("p(1,1), p(1,5), p(1,6), p(1,8), p(1,9), p(1,10), p(2,2), p(2,3), p(2,4), p(2,7), p(2,11), p(2,12)",""), True),
        Example(("p(1,1), p(1,2), p(1,7), p(1,8), p(1,10), p(1,11), p(2,3), p(2,4), p(2,5), p(2,6), p(2,9), p(2,12)",""), True)
    ]
    
    # some of the 29 not valid possible placements (in total 2048 possible placements)
    negative_examples : 'list[Example]' = [
        Example(("p(1,1), p(1,10), p(1,12), p(1,2), p(1,3), p(1,4), p(1,5), p(1,6), p(1,7), p(1,8), p(2,11), p(2,9)",""), False),
        Example(("p(1,1), p(1,10), p(1,11), p(1,2), p(1,3), p(1,4), p(1,5), p(1,6), p(1,8), p(2,12), p(2,7), p(2,9)",""), False),
        Example(("p(1,1), p(1,10), p(1,12), p(1,2), p(1,3), p(1,4), p(1,5), p(1,6), p(1,8), p(2,11), p(2,7), p(2,9)",""), False),
        Example(("p(1,1), p(1,11), p(1,2), p(1,3), p(1,4), p(1,5), p(1,6), p(1,8), p(2,10), p(2,12), p(2,7), p(2,9)",""), False),
        Example(("p(1,1), p(1,10), p(1,11), p(1,12), p(1,2), p(1,3), p(1,4), p(1,5), p(1,7), p(1,9), p(2,6), p(2,8)",""), False),
        Example(("p(1,1), p(1,11), p(1,12), p(1,2), p(1,3), p(1,4), p(1,5), p(1,8), p(1,9), p(2,10), p(2,6), p(2,7)",""), False),
        Example(("p(1,1), p(1,11), p(1,12), p(1,2), p(1,3), p(1,4), p(1,6), p(1,9), p(2,10), p(2,5), p(2,7), p(2,8)",""), False),
        Example(("p(1,1), p(1,12), p(1,2), p(1,3), p(1,4), p(1,6), p(1,9), p(2,10), p(2,11), p(2,5), p(2,7), p(2,8)",""), False),
        Example(("p(1,1), p(1,12), p(1,2), p(1,3), p(1,4), p(1,7), p(1,8), p(1,9), p(2,10), p(2,11), p(2,5), p(2,6)",""), False),
        Example(("p(1,1), p(1,10), p(1,12), p(1,2), p(1,3), p(1,4), p(1,9), p(2,11), p(2,5), p(2,6), p(2,7), p(2,8)",""), False)
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "sum_partition", "2"), True),
        ModeDeclaration(("1", "count_partition", "2"), True)
    ]
    
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("2", "sum_partition", "2", "positive"), False),
        ModeDeclaration(("2", "count_partition", "2", "positive"), False),
        ModeDeclaration(("1", "partition", "1", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def set_partition_sum_cardinality_and_square():
    '''
    Inspired by: http://www.hakank.org/answer_set_programming/set_partition.lp
    Set partition problem: given the set S = {1, 2, ..., n}, 
    find two sets A and B such that:
    - A U B = S
    - sum(A) = sum(B)
    - |A| = |B|
    - sum of squares of A = sum of squares of B 
    -------------
    Given:
    #const n = 12. 
    val(1..n).
    partition(1..2).
    % split the numbers in two partitions
    1 { p(P, I) : partition(P) } 1 :- val(I).
    % symmetry breaking
    p(1,1).
    % sum of squares
    sq(Partition,Val):- p(Partition,V), Val = V*V.
    Learn (6 rules):
    % NOTE: the aggregation on p/2 can be avoided when the one on sq/2 is used (for this setting)
    count_partition(Count,Partition):-
        partition(Partition),
        Count = #count{I : p(Partition,I)}.
    :- count_partition(P0, S1), count_partition(P1, S2), P0 != P1, S1 != S2.
    sum_partition_sq(Sum,Partition):-
        partition(Partition),
        Sum = #sum{I : sq(Partition,I)}.
    :- sum_partition_sq(P0, S1), sum_partition_sq(P1, S2), P0 != P1, S1 != S2.
    '''

    background : 'list[str]' = [
        "#const n = 12.",
        "val(1..n).",
        "partition(1..2).",
        "1 { p(P, I) : partition(P) } 1 :- val(I).",
        "p(1,1).",
        "sq(Partition,Val):- p(Partition,V), Val = V*V."
    ]
    
    # only one solution
    positive_examples : 'list[Example]' = [
        Example(("p(1,1), p(2,2), p(1,3), p(2,4), p(2,5), p(2,6), p(1,7), p(1,8), p(1,9), p(2,10), p(1,11), p(2,12)", ""), True)
    ]
    
    # some of the 2048 possible placements
    negative_examples : 'list[Example]' = [
        Example(("p(1,1), p(1,2), p(2,3), p(2,4), p(2,5), p(1,6), p(2,7), p(1,8), p(2,9), p(1,10), p(2,11), p(1,12)",""), False),
        Example(("p(1,1), p(1,2), p(1,3), p(1,4), p(1,5), p(1,6), p(1,7), p(1,8), p(2,9), p(2,10), p(1,11), p(2,12)",""), False),
        Example(("p(1,1), p(1,2), p(1,3), p(1,4), p(1,5), p(2,6), p(1,7), p(2,8), p(2,9), p(1,10), p(1,11), p(2,12)",""), False),
        Example(("p(1,1), p(2,2), p(1,3), p(1,4), p(1,5), p(2,6), p(1,7), p(2,8), p(1,9), p(2,10), p(2,11), p(1,12)",""), False),
        Example(("p(1,1), p(2,2), p(2,3), p(1,4), p(2,5), p(2,6), p(2,7), p(1,8), p(2,9), p(1,10), p(2,11), p(1,12)",""), False)
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "sum_partition_sq", "2"), True),
        ModeDeclaration(("1", "count_partition", "2"), True)
    ]
    
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("2", "sum_partition_sq", "2", "positive"), False),
        ModeDeclaration(("2", "count_partition", "2", "positive"), False),
        ModeDeclaration(("1", "partition", "1", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def set_partition_new(also_count : bool):
    '''
    Inspired by: http://www.hakank.org/answer_set_programming/set_partition.lp
    Set partition problem: given the set S = {1, 2, ..., n}, 
    find two sets A and B such that:
    - A U B = S
    - sum(A) = sum(B)
    -------------
    Given:
    partition(1..2).
    % split the numbers in two partitions
    1 { p(P, I) : partition(P) } 1 :- val(I).
    % symmetry breaking
    p(1,1).
    Learn:
    sum_partition(Sum,Partition):-
        partition(Partition),
        Sum = #sum{I : p(Partition,I)}.
    :- sum_partition(P0, S1), sum_partition(P1, S2), P0 != P1, S1 != S2.
    '''

    background : 'list[str]' = [
        "val(2).",
        "val(4).",
        "val(5).",
        "val(6).",
        "val(8).",
        "val(9).",
        "partition(1..2).",
        "1 { p(P, I) : partition(P) } 1 :- val(I).",
        "p(1,2)."
    ]
    
    # all the solutions
    positive_examples : 'list[Example]' = [
        Example(("p(1,2), p(1,6), p(1,9), p(2,4), p(2,5), p(2,8)",""), True) # ok also for count
    ]
    if not also_count:
        positive_examples.append(Example(("p(1,2), p(1,4), p(1,5), p(1,6), p(2,8), p(2,9)",""), True))
    
    # remaining
    negative_examples : 'list[Example]' = [
        Example(("p(1,2), p(1,4), p(1,5), p(1,6), p(1,8), p(1,9)",""), False),
        Example(("p(1,2), p(1,5), p(1,6), p(1,8), p(1,9), p(2,4)",""), False),
        Example(("p(1,2), p(1,4), p(1,6), p(1,8), p(1,9), p(2,5)",""), False),
        Example(("p(1,2), p(1,6), p(1,8), p(1,9), p(2,4), p(2,5)",""), False),
        Example(("p(1,2), p(1,4), p(1,5), p(1,8), p(1,9), p(2,6)",""), False),
        Example(("p(1,2), p(1,5), p(1,8), p(1,9), p(2,4), p(2,6)",""), False),
        Example(("p(1,2), p(1,4), p(1,8), p(1,9), p(2,5), p(2,6)",""), False),
        Example(("p(1,2), p(1,8), p(1,9), p(2,4), p(2,5), p(2,6)",""), False),
        Example(("p(1,2), p(1,4), p(1,5), p(1,6), p(1,9), p(2,8)",""), False),
        Example(("p(1,2), p(1,5), p(1,6), p(1,9), p(2,4), p(2,8)",""), False),
        Example(("p(1,2), p(1,4), p(1,6), p(1,9), p(2,5), p(2,8)",""), False),
        Example(("p(1,2), p(1,4), p(1,5), p(1,9), p(2,6), p(2,8)",""), False),
        Example(("p(1,2), p(1,5), p(1,9), p(2,4), p(2,6), p(2,8)",""), False),
        Example(("p(1,2), p(1,4), p(1,9), p(2,5), p(2,6), p(2,8)",""), False),
        Example(("p(1,2), p(1,9), p(2,4), p(2,5), p(2,6), p(2,8)",""), False),
        Example(("p(1,2), p(1,4), p(1,5), p(1,6), p(1,8), p(2,9)",""), False),
        Example(("p(1,2), p(1,5), p(1,6), p(1,8), p(2,4), p(2,9)",""), False),
        Example(("p(1,2), p(1,4), p(1,6), p(1,8), p(2,5), p(2,9)",""), False),
        Example(("p(1,2), p(1,6), p(1,8), p(2,4), p(2,5), p(2,9)",""), False),
        Example(("p(1,2), p(1,4), p(1,5), p(1,8), p(2,6), p(2,9)",""), False),
        Example(("p(1,2), p(1,5), p(1,8), p(2,4), p(2,6), p(2,9)",""), False),
        Example(("p(1,2), p(1,4), p(1,8), p(2,5), p(2,6), p(2,9)",""), False),
        Example(("p(1,2), p(1,8), p(2,4), p(2,5), p(2,6), p(2,9)",""), False),
        Example(("p(1,2), p(1,5), p(1,6), p(2,4), p(2,8), p(2,9)",""), False),
        Example(("p(1,2), p(1,4), p(1,6), p(2,5), p(2,8), p(2,9)",""), False),
        Example(("p(1,2), p(1,6), p(2,4), p(2,5), p(2,8), p(2,9)",""), False),
        Example(("p(1,2), p(1,4), p(1,5), p(2,6), p(2,8), p(2,9)",""), False),
        Example(("p(1,2), p(1,5), p(2,4), p(2,6), p(2,8), p(2,9)",""), False),
        Example(("p(1,2), p(1,4), p(2,5), p(2,6), p(2,8), p(2,9)",""), False),
        Example(("p(1,2), p(2,4), p(2,5), p(2,6), p(2,8), p(2,9)",""), False)
    ]
    
    if also_count:
        negative_examples.append(Example(("p(1,2), p(1,4), p(1,5), p(1,6), p(2,8), p(2,9)",""), False))
        
    
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "sum_partition", "2"), True)
    ]
    if also_count:
        language_bias_head.append(ModeDeclaration(("1", "count_partition", "2"), True))
    
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("2", "sum_partition", "2", "positive"), False),
        ModeDeclaration(("1", "partition", "1", "positive"), False)
    ]
    if also_count:
        language_bias_body.append(ModeDeclaration(("2", "count_partition", "2", "positive"), False))
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)


def latin_square():
    '''
    With aggregates: the same element cannot repeat in the same 
    row or column.
    Given:
    cell(1..3).
    val(1..3).
    size(3).
    1{x(R,C,N) : val(N)}1:- cell(R), cell(C).
    x(1,1,1).
    Learn:
    count_row(R,S):- S = #count{V : x(R,C,V), cell(C)}, cell(R).
    count_col(C,S):- S = #count{V : x(R,C,V), cell(R)}, cell(C).
    :- count_col(Col,C), cell(Col), size(S), C != S.
    :- count_row(Row,C), cell(Row), size(S), C != S.
    '''
    # https://en.wikipedia.org/wiki/Latin_square
    background : 'list[str]' = [
        "cell(1..3).",
        "val(1..3).",
        "size(3).",
        "1{x(R,C,N) : val(N)}1:- cell(R), cell(C).",
        "x(1,1,1)." # to remove some symmetries
    ]
    
    # all the existing solutions (4)
    positive_examples : 'list[Example]' = [
        Example(("x(1,1,1), x(1,3,2), x(1,2,3), x(2,2,1), x(2,1,2), x(2,3,3), x(3,3,1), x(3,2,2), x(3,1,3)", ""), True),
        Example(("x(1,1,1), x(1,3,2), x(1,2,3), x(2,3,1), x(2,2,2), x(2,1,3), x(3,2,1), x(3,1,2), x(3,3,3)", ""), True),
        Example(("x(1,1,1), x(1,2,2), x(1,3,3), x(2,3,1), x(2,1,2), x(2,2,3), x(3,2,1), x(3,3,2), x(3,1,3)", ""), True),
        Example(("x(1,1,1), x(1,2,2), x(1,3,3), x(2,2,1), x(2,3,2), x(2,1,3), x(3,3,1), x(3,1,2), x(3,2,3)", ""), True)
    ]
    
    # all the solutions with only one of the two constraints -> too many
    # I select only 20 of them
    negative_examples : 'list[Example]' = [
        Example(("x(1,1,1), x(1,2,3), x(1,3,3), x(2,1,3), x(2,2,1), x(2,3,2), x(3,1,2), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,1), x(1,2,2), x(1,3,3), x(2,1,3), x(2,2,1), x(2,3,2), x(3,1,1), x(3,2,3), x(3,3,2)",""), False),
        Example(("x(1,1,1), x(1,2,2), x(1,3,3), x(2,1,1), x(2,2,3), x(2,3,2), x(3,1,3), x(3,2,1), x(3,3,2)",""), False),
        Example(("x(1,1,1), x(1,2,1), x(1,3,2), x(2,1,2), x(2,2,3), x(2,3,3), x(3,1,3), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,1), x(1,2,2), x(1,3,3), x(2,1,3), x(2,2,2), x(2,3,1), x(3,1,2), x(3,2,1), x(3,3,3)",""), False),
        Example(("x(1,1,1), x(1,2,3), x(1,3,2), x(2,1,1), x(2,2,3), x(2,3,2), x(3,1,3), x(3,2,1), x(3,3,2)",""), False),
        Example(("x(1,1,1), x(1,2,3), x(1,3,2), x(2,1,3), x(2,2,1), x(2,3,1), x(3,1,2), x(3,2,2), x(3,3,3)",""), False),
        Example(("x(1,1,1), x(1,2,2), x(1,3,3), x(2,1,3), x(2,2,1), x(2,3,2), x(3,1,2), x(3,2,1), x(3,3,3)",""), False),
        Example(("x(1,1,1), x(1,2,1), x(1,3,1), x(2,1,3), x(2,2,3), x(2,3,3), x(3,1,2), x(3,2,2), x(3,3,2)",""), False),
        Example(("x(1,1,1), x(1,2,3), x(1,3,2), x(2,1,2), x(2,2,3), x(2,3,1), x(3,1,2), x(3,2,1), x(3,3,3)",""), False),
        Example(("x(1,1,1), x(1,2,3), x(1,3,2), x(2,1,2), x(2,2,1), x(2,3,3), x(3,1,1), x(3,2,3), x(3,3,2)",""), False),
        Example(("x(1,1,1), x(1,2,2), x(1,3,2), x(2,1,3), x(2,2,1), x(2,3,3), x(3,1,2), x(3,2,3), x(3,3,1)",""), False),
        Example(("x(1,1,1), x(1,2,1), x(1,3,3), x(2,1,2), x(2,2,2), x(2,3,1), x(3,1,3), x(3,2,3), x(3,3,2)",""), False),
        Example(("x(1,1,1), x(1,2,1), x(1,3,2), x(2,1,3), x(2,2,3), x(2,3,3), x(3,1,2), x(3,2,2), x(3,3,1)",""), False),
        Example(("x(1,1,1), x(1,2,3), x(1,3,1), x(2,1,2), x(2,2,2), x(2,3,3), x(3,1,3), x(3,2,1), x(3,3,2)",""), False),
        Example(("x(1,1,1), x(1,2,2), x(1,3,3), x(2,1,3), x(2,2,1), x(2,3,2), x(3,1,3), x(3,2,1), x(3,3,2)",""), False),
        Example(("x(1,1,1), x(1,2,3), x(1,3,1), x(2,1,3), x(2,2,1), x(2,3,2), x(3,1,2), x(3,2,2), x(3,3,3)",""), False),
        Example(("x(1,1,1), x(1,2,2), x(1,3,2), x(2,1,3), x(2,2,1), x(2,3,1), x(3,1,2), x(3,2,3), x(3,3,3)",""), False),
        Example(("x(1,1,1), x(1,2,3), x(1,3,2), x(2,1,3), x(2,2,1), x(2,3,2), x(3,1,1), x(3,2,2), x(3,3,3)",""), False),
        Example(("x(1,1,1), x(1,2,1), x(1,3,2), x(2,1,2), x(2,2,2), x(2,3,3), x(3,1,3), x(3,2,3), x(3,3,1)",""), False)
    ]
    
    language_bias_head : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "count_row", "2"), True),
        ModeDeclaration(("1", "count_col", "2"), True)
    ]
    
    language_bias_body : 'list[ModeDeclaration]' = [
        ModeDeclaration(("1", "count_row", "2", "positive"), False),
        ModeDeclaration(("1", "count_col", "2", "positive"), False),
        ModeDeclaration(("1", "cell", "1", "positive"), False),
        ModeDeclaration(("1", "size", "1", "positive"), False)
    ]
    
    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)

def user_defined():
    '''
    Stub for user-defined examples.
    Place here your example.
    '''
    # background knowledge
    background : 'list[str]' = []

    # positive examples
    positive_examples : 'list[Example]' = []

    # negative examples
    negative_examples : 'list[Example]' = []

    # mode bias for the head
    language_bias_head : 'list[ModeDeclaration]' = []

    # mode bias for the body
    language_bias_body : 'list[ModeDeclaration]' = []

    return Program(background, positive_examples, negative_examples, language_bias_head, language_bias_body)

def run_example(example : str) -> Program:
    '''
    Runs the selected example
    '''
    if example == "coin":
        return coin_example()
    elif example == "even_odd":
        return even_odd_example()
    elif example == "animals_bird":
        return animals_bird_example()
    # elif example == "penguin":
    #     return penguin_example()
    elif example == "coloring":
        return coloring_example()
    elif example == "adjacent_to_red":
        return adjacent_to_red_example()
    elif example == "grandparent":
        return grandparent_example()
    elif example == "sudoku":
        return sudoku()
    elif example == "euclid":
        return euclid_example()
    elif example == "subset_sum":
       return subset_sum()
    elif example == "subset_sum_double":
        return subset_sum_double()
    elif example == "subset_sum_double_and_sum":
        return subset_sum_double_and_sum()
    elif example == "subset_sum_double_and_prod":
        return subset_sum_double_and_prod()
    elif example == "subset_sum_triple":
        return subset_sum_triple()
    elif example == "knapsack":
        return knapsack()
    elif example == "4queens":
        return n_4queens()
    elif example == "5queens":
        return n_5queens()
    elif example == "clique":
        return clique()
    elif example == "hamming_0":
        return hamming(0, False)
    elif example == "hamming_1":
        return hamming(1, False)
    # elif example == "harder_hamming_0":
    #     return hamming(0, True)
    # elif example == "harder_hamming_1":
    #     return hamming(1, True)
    # elif example == "partition":
    #     rerurn partition()
    elif example == "magic_square_no_diag":
        return magic_square_no_diag()
    elif example == "latin_square":
        return latin_square()
    elif example == "set_partition_sum":
        return set_partition_sum()
    elif example == "set_partition_sum_and_cardinality":
        return set_partition_sum_and_cardinality()
    elif example == "set_partition_sum_new":
        return set_partition_new(False)
    elif example == "set_partition_sum_and_cardinality_new":
        return set_partition_new(True)
    elif example == "set_partition_sum_cardinality_and_square":
        return set_partition_sum_cardinality_and_square()
    elif example == "user_defined":
        return user_defined()
    else:
        print_error_and_exit("Example not found")
    
    return Program([],[],[],[],[])