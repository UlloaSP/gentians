% Choose one slot encoding: no gaps, nondecreasing modes, sorted equal-mode tuples.
% Equal modes are contiguous; adjacent tuple checks therefore suffice.
% The decoder and duplicate checks rely on these ordering invariants.

% CONSTRAINT. Slots are filled from 0 upwards without gaps.
%   Section  head or body.
%   Slot     an occupied slot above 0 whose predecessor is empty.
% The same two-literal body could otherwise sit in slots {0,1}, {0,2}, {1,2}...
%   pruned: selected(body,1,M) with no selected(body,0,_)
%   kept:   selected(body,0,M), selected(body,1,N)
:- selected_slot(Section, Slot), Slot > 0, not selected_slot(Section, Slot-1).

% CONSTRAINT. Within a section, mode ids never decrease along the slots. It
% fixes the order of literals of different modes and makes equal modes
% contiguous.
%   Section       head or body.
%   Slot0, Slot1  two occupied slots, Slot0 first.
%   Mode0, Mode1  their mode ids.
% With mode 4 = edge/2 and mode 7 = red/1:
%   pruned: selected(body,0,7), selected(body,1,4)     red(..), edge(..)
%   kept:   selected(body,0,4), selected(body,1,7)     edge(..), red(..)
:- selected(Section, Slot0, Mode0), selected(Section, Slot1, Mode1), Slot0 < Slot1, Mode0 > Mode1.

% DEFINITION, local helper. same_mode_tuple_gt(Section, Slot0, Slot1): two
% adjacent literals of the same mode are written in descending order.
%   Section  head or body.
%   Slot0    a slot.
%   Slot1    the next slot (Slot0 + 1), holding the same mode.
% It holds when, at the first placeholder where the two literals differ, the
% earlier literal has the greater variable id. Arg is that placeholder: the
% two #count aggregates state that every earlier placeholder (Prev < Arg)
% holds equal variables in both, which makes the comparison lexicographic.
% Used only by the constraint below.
same_mode_tuple_gt(Section, Slot0, Slot1) :-
    selected(Section, Slot0, Mode),
    selected(Section, Slot1, Mode),
    Slot1 = Slot0 + 1,
    mode_variable_arg(Mode, Arg),
    var_at(Section, Slot0, Arg, Left),
    var_at(Section, Slot1, Arg, Right),
    Left > Right,
    Before = #count{Prev : mode_variable_arg(Mode, Prev), Prev < Arg},
    Before = #count{
        Prev : mode_variable_arg(Mode, Prev), Prev < Arg,
        var_at(Section, Slot0, Prev, Same),
        var_at(Section, Slot1, Prev, Same)
    }.

% CONSTRAINT. Adjacent literals of the same mode appear in ascending order of
% their variable tuples. Identical tuples pass here and are rejected as
% duplicates by pruning/redundancy/literals.lp.
%   Section, Slot0, Slot1  the adjacent pair found in descending order.
%   pruned: :- edge(V0,V2), edge(V0,V1).      (0,2) before (0,1)
%   kept:   :- edge(V0,V1), edge(V0,V2).
:- same_mode_tuple_gt(Section, Slot0, Slot1).
