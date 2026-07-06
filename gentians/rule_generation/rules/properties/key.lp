% Closed-world key property.
%
% Python emits key_pred(Pred,Key) plus key_arg(Key,Arg) when the listed argument
% positions form a key for predicate Pred. Two true Pred tuples cannot share all
% key arguments while differing elsewhere.
%
% Shared atom shapes used here:
% - key_pred(Pred,Key): property fact. Pred is predicate id; Key is key id.
% - key_arg(Key,Arg): argument Arg belongs to key Key.
% - positive_body_literal/4 and negative_body_literal/4: selected body atoms.
% - var_at(body,Slot,Arg,Var): variable at predicate argument Arg.
% - known_distinct_vars(Out0,Out1): comparison module proves variables differ.

% Python fact contract:
% - key_pred(Pred,Key): emitted by Python when predicate id Pred has key id Key.
% - key_arg(Key,Arg): emitted by Python for every zero-based argument Arg that
%   participates in key Key.
% Python fact detail: key_pred(Pred,Key) assigns key id Key to predicate id Pred.
#defined key_pred/2.
% Python fact detail: key_arg(Key,Arg) lists one zero-based argument Arg participating in key Key.
#defined key_arg/2.

% Rule: two literals differ on at least one key argument.
% Slot0 and Slot1 are body literals being compared. Key is key id. Arg is one
% key argument. Left and Right are variables at Arg. If Left != Right, the two
% tuples do not share the full key.
key_inputs_differ(Slot0,Slot1,Key):-
    key_arg(Key,Arg),
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    Left != Right.

% Rule: two body slots differ in at least one argument variable.
% Slot0 and Slot1 are body slots. Arg is any argument position common to both.
% Left and Right are variables at Arg. Difference means the full tuples differ.
slot_vars_differ(body,Slot0,body,Slot1):-
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    Left != Right.

% Constraint: reject two positive tuples sharing key but differing elsewhere.
% Slot0 and Slot1 are ordered positive literals for Pred. key_pred supplies Key.
% not key_inputs_differ means all key args match. slot_vars_differ means some
% non-key or key-independent position differs, violating uniqueness.
:- positive_body_literal(Slot0,_,Pred,_),
    positive_body_literal(Slot1,_,Pred,_),
    Slot0 < Slot1,
    key_pred(Pred,Key),
    not key_inputs_differ(Slot0,Slot1,Key),
    slot_vars_differ(body,Slot0,body,Slot1).

% Rule: derive non-key output arguments for a keyed predicate.
% Pred is predicate id, Key is key id, Arg ranges over all argument positions of
% positive Pred literals. not key_arg(Key,Arg) keeps only positions determined
% by the key rather than part of the key.
key_output_arg(Pred,Key,Arg):-
    positive_body_literal(_,_,Pred,Arity),
    key_pred(Pred,Key),
    Arg = 0..Arity-1,
    not key_arg(Key,Arg).

% Constraint: reject negative literal contradicted by positive keyed tuple.
% PosSlot and NegSlot share all key inputs for Pred/Key. Output is a non-key
% argument. If positive output Out0 and negative output Out1 are known distinct,
% then the negative literal is implied by key uniqueness and redundant.
:- positive_body_literal(PosSlot,_,Pred,_),
    negative_body_literal(NegSlot,_,Pred,_),
    key_pred(Pred,Key),
    not key_inputs_differ(PosSlot,NegSlot,Key),
    key_output_arg(Pred,Key,Output),
    var_at(body,PosSlot,Output,Out0),
    var_at(body,NegSlot,Output,Out1),
    known_distinct_vars(Out0,Out1).
