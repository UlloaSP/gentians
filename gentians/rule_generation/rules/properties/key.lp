% Closed-world key property.
%
% Python emits key_pred(Pred,Key) plus key_arg(Key,Arg) when the listed argument
% positions form a key for predicate Pred. Two true Pred tuples cannot share all
% key arguments while differing elsewhere. A key is a functional dependency from
% key arguments to every non-key argument, so this file exports
% functional_set_pred/3 and functional_set_arg/2 instead of duplicating
% functional dependency pruning here.
%
% Shared atom shapes used here:
% - key_pred(Pred,Key): property fact. Pred is predicate id; Key is key id.
% - key_arg(Key,Arg): argument Arg belongs to key Key.
% - functional_set_pred(Pred,Fd,Output): derived property atom consumed by
%   functional_set.lp. This file uses Fd=key(Key) to avoid numeric id clashes
%   with Python-emitted functional dependency ids.
% - functional_set_arg(Fd,Input): derived determinant argument atom consumed by
%   functional_set.lp.
% - positive_body_literal(Slot,Mode,Pred,Arity): selected positive body atom.

% Python fact contract:
% - key_pred(Pred,Key): emitted by Python when predicate id Pred has key id Key.
% - key_arg(Key,Arg): emitted by Python for every zero-based argument Arg that
%   participates in key Key.
% Python fact detail: key_pred(Pred,Key) assigns key id Key to predicate id Pred.
#defined key_pred/2.
% Python fact detail: key_arg(Key,Arg) lists one zero-based argument Arg participating in key Key.
#defined key_arg/2.

% Rule: key arguments are determinant arguments for the derived FD.
% Key is the key id. Arg is one zero-based key argument. key(Key) is a symbolic
% FD id used only inside ASP so it cannot collide with Python integer Fd ids.
functional_set_arg(key(Key),Arg):- key_arg(Key,Arg).

% Rule: each non-key argument is determined by the key.
% Pred is predicate id. Key is key id. Output ranges over every zero-based
% argument position of a selected positive Pred literal. not key_arg(Key,Output)
% keeps only non-key outputs. functional_set.lp owns all pruning that follows
% from this derived functional dependency.
functional_set_pred(Pred,key(Key),Output):-
    positive_body_literal(_,_,Pred,Arity),
    key_pred(Pred,Key),
    Output = 0..Arity-1,
    not key_arg(Key,Output).
