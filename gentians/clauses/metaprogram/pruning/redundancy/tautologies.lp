% Lin and Chen, "Discovering Classes of Strongly Equivalent Logic Programs",
% IJCAI 2005, Theorem 5 (the 0-1-0 problem): a rule is strongly equivalent to
% the empty program if a positive body atom also occurs in its head or its
% default-negated body. https://cse.hkust.edu.hk/faculty/flin/papers/selp-disc-ijcai05.pdf
%
% Compare complete signed atoms: same predicate, recursive term shape and
% variable bindings. Positive/negative body overlap makes the body impossible.
% Positive body/head overlap is a tautology for normal or disjunctive heads;
% choice and cardinality heads need a separate argument and are not pruned here.

:- positive_body_literal(PosSlot, _, Pred, Arity),
    negative_body_literal(NegSlot, _, Pred, Arity),
    same_term_bindings(body, PosSlot, body, NegSlot).

:- selected(head, HeadSlot, HeadMode),
    plain_disjunctive_head_mode(HeadMode),
    head_literal(HeadSlot, HeadMode, Pred, Arity),
    positive_body_literal(BodySlot, _, Pred, Arity),
    same_term_bindings(head, HeadSlot, body, BodySlot).
