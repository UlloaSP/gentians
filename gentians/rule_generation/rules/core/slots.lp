% Core slot skeleton for generated clauses.
%
% This file creates the finite search grid used by the generator:
% variable ids, possible head slots, possible body slots, and one optional mode
% assignment per slot.  It also owns canonical slot ordering constraints that
% remove duplicate encodings of the same clause before Python sees a model.
%
% Shared atom shapes used here:
% - max_vars(Max): Python fact. Max is the configured number of generated
%   variables, encoded as ids 0..Max-1.
% - max_body(Max): Python fact. Max is maximum body literals.
% - max_head(Max): Python fact. Max is the maximum number of head literals.
% - mode(Section,Mode,Pred,Arity,Recall): Python fact. Section is head/body;
%   Mode is the generator mode id; Pred is the predicate id for normal modes;
%   Arity is number of arguments; Recall is the per-mode recall cap.
% - selected(Section,Slot,Mode): this file's choice atom. It means literal
%   slot Slot in Section uses generator mode Mode.
% - var_at(Section,Slot,Arg,Var): defined in core/arguments.lp. It means
%   argument Arg of selected literal Section/Slot uses generated variable Var.

% Python fact contract:
% - max_vars(Max): emitted from task #maxv. Max is count
%   of generated variable ids; this module creates var(0)..var(Max-1).
% - max_body(Max): emitted from task #maxbl. This module uses it as body slot count.
% - max_head(Max): emitted from task #maxhl. Max is
%   number of available head slots.
% - mode(Section,Mode,Pred,Arity,Recall): emitted by Python for every available
%   hypothesis mode. Section is head/body; Mode is unique mode id; Pred is
%   predicate id for normal modes; Arity is rendered arity; Recall is mode cap.
% Python fact detail: max_vars(Max) comes from task #maxv; Max is count of available generated variables V0..V(Max-1).
#defined max_vars/1.
% Python fact detail: max_body(Max) comes from task #maxbl.
#defined max_body/1.
% Python fact detail: max_head(Max) comes from task #maxhl.
#defined max_head/1.
% Python fact detail: mode(Section,Mode,Pred,Arity,Recall) is emitted per hypothesis mode; Section=head/body, Mode=id, Pred=predicate id for normal modes, Arity=argument count, Recall=mode cap.
#defined mode/5.

% Rule: create all variable ids allowed in candidate clauses.
% Max comes from max_vars(Max). Var ranges from 0 to Max-1.
% Later modules use var(Var) as the domain for var_at(...,Var).
var(0..Max-1):- max_vars(Max).

% Rule: create all possible head slot ids.
% Max comes from max_head(Max). Slot ranges from 0 to Max-1.
% The Max > 0 guard avoids an invalid 0..-1 interval.
head_slot(0..Max-1):- max_head(Max), Max > 0.

% Rule: create all possible body slot ids.
% Max comes from max_body(Max). Slot ranges from 0 to Max-1.
% The Max > 0 guard avoids an invalid 0..-1 interval.
body_slot(0..Max-1):- max_body(Max), Max > 0.

% Fact: section_order(head,0) gives head literals lower structural order.
% Used when comparing literals across sections for duplicate pruning.
section_order(head,0).

% Fact: section_order(body,1) gives body literals order after head literals.
% Used with tuple comparisons such as (Order,Slot) < (OtherOrder,OtherSlot).
section_order(body,1).

% Choice rule: each head slot may contain zero or one head mode.
% Slot comes from head_slot(Slot). Mode ranges over mode(head,Mode,...).
% The lower bound 0 allows unused slots; the upper bound 1 prevents two
% literals occupying the same head slot.
0 { selected(head,Slot,Mode) : mode(head,Mode,_,_,_) } 1:- head_slot(Slot).

% Choice rule: each body slot may contain zero or one body mode.
% Slot comes from body_slot(Slot). Mode ranges over mode(body,Mode,...).
% The lower bound 0 allows short bodies; the upper bound 1 keeps one literal
% per slot.
0 { selected(body,Slot,Mode) : mode(body,Mode,_,_,_) } 1:- body_slot(Slot).

% Rule: selected_slot(Section,Slot) records that a slot is occupied.
% Section is head/body. Slot is the occupied slot id. Mode is anonymous because
% only occupancy matters to gapless and count rules.
selected_slot(Section,Slot):- selected(Section,Slot,_).

% Constraint: occupied slots must be gapless from slot 0.
% If Slot > 0 is selected in Section, then Slot-1 must also be selected.
% This removes equivalent clauses that differ only by shifting literals to
% later empty slots.
:- selected_slot(Section,Slot), Slot > 0, not selected_slot(Section,Slot-1).

% Constraint: selected mode ids must be nondecreasing inside each section.
% Section is head/body. Slot0 and Slot1 are two occupied slots with Slot0 before
% Slot1. Mode0 > Mode1 is rejected, so permutations of different literal modes
% are represented once.
:- selected(Section,Slot0,Mode0), selected(Section,Slot1,Mode1), Slot0 < Slot1, Mode0 > Mode1.

% Rule: detect same-mode tuples that are lexicographically descending.
% Section is head/body. Slot0 and Slot1 are adjacent slots with the same Mode.
% Mode ordering makes repeated modes contiguous, so adjacent checks are enough.
% Arity is the mode arity. Arg is the first argument position where the two
% variable tuples differ. Left and Right are the variables at that first
% differing position. The #count expression proves all previous Prev positions
% use the same variable in both slots. If Left > Right, Slot0's tuple should
% have appeared after Slot1, so same_mode_tuple_gt marks a canonical duplicate.
same_mode_tuple_gt(Section,Slot0,Slot1):-
    selected(Section,Slot0,Mode),
    selected(Section,Slot1,Mode),
    Slot1 = Slot0 + 1,
    mode(Section,Mode,_,Arity,_),
    Arg = 0..Arity-1,
    var_at(Section,Slot0,Arg,Left),
    var_at(Section,Slot1,Arg,Right),
    Left > Right,
    Arg = #count{
        Prev : Prev = 0..Arg-1,
        var_at(Section,Slot0,Prev,Same),
        var_at(Section,Slot1,Prev,Same)
    }.

% Constraint: reject descending variable tuples for repeated same-mode literals.
% This canonicalizes clauses such as p(V1),p(V0) into only p(V0),p(V1) when
% both literals use the same Mode.
:- same_mode_tuple_gt(Section,Slot0,Slot1).
