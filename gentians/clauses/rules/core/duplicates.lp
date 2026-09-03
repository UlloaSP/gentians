% Final duplicate-literal pruning.
%
% Shared atom shapes used here:
% - normal_mode(Mode): derived atom. Mode is a normal predicate mode.
% - selected(Section,Slot,Mode): defined in core/slots.lp.
% - normal_literal(Section,Slot,Mode,Pred,Arity): core/literals.lp alias.
% - section_order(Section,Order): defined in core/slots.lp.

% Cross-module contract:
% - normal_mode(Mode): derived by core/literals.lp. Used here to distinguish
%   normal duplicate pruning from operator duplicate pruning.

% Rule: detect duplicate normal predicate literals.
% Section0/Slot0 and Section1/Slot1 are ordered by section_order and Slot.
% Pred/Arity must match. same_vars/4 proves both literals use the same term tuple.
same_normal_literal(Section0,Slot0,Section1,Slot1):-
    normal_literal(Section0,Slot0,Mode0,Pred,Arity),
    normal_literal(Section1,Slot1,Mode1,Pred,Arity),
    section_order(Section0,Order0),
    section_order(Section1,Order1),
    (Order0,Slot0) < (Order1,Slot1),
    Mode0 != Mode1,
    same_vars(Section0,Slot0,Section1,Slot1).

same_normal_literal(Section,Slot0,Section,Slot1):-
    normal_literal(Section,Slot0,Mode,Pred,Arity),
    normal_literal(Section,Slot1,Mode,Pred,Arity),
    Slot1 = Slot0 + 1,
    same_vars(Section,Slot0,Section,Slot1).

% Constraint: reject duplicated normal predicate literals.
% A clause containing the same predicate with the same variables twice has no
% additional meaning and creates duplicate hypotheses.
:- same_normal_literal(Section0,Slot0,Section1,Slot1).

% Rule: detect duplicate non-normal literals with the same mode and variables.
% Non-normal modes only occur in body slots. Mode ordering makes equal modes
% contiguous, so adjacent checks catch every duplicate run.
same_mode_literal(body,Slot0,body,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    not normal_mode(Mode),
    Slot1 = Slot0 + 1,
    same_vars(body,Slot0,body,Slot1).

% Constraint: reject duplicated non-normal literals.
% Same Mode and same variable tuple would render the same operator/arithmetic/
% aggregate literal twice.
:- same_mode_literal(Section0,Slot0,Section1,Slot1).
