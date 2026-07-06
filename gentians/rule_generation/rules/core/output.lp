% Output encoding for Python.
%
% This file performs final duplicate-literal pruning and emits lit/4 atoms.
% lit/4 is the only shown predicate consumed by HypothesisSpaceGenerator.
%
% Shared atom shapes used here:
% - normal_mode(Mode): derived atom. Mode is a normal predicate mode.
% - max_vars(Base): Python fact. Base is used for positional integer encoding.
% - selected(Section,Slot,Mode): defined in core/slots.lp.
% - normal_literal(Section,Slot,Mode,Pred,Arity): core/literals.lp alias.
% - mode(Section,Mode,Pred,Arity,Recall): Python fact.
% - var_at(Section,Slot,Arg,Var): defined in core/arguments.lp.
% - section_order(Section,Order): defined in core/slots.lp.

% Cross-module contract:
% - normal_mode(Mode): derived by core/literals.lp. Used here to distinguish
%   normal duplicate pruning from operator duplicate pruning.
% - max_vars(Base): emitted by Python from args.max_variables. Base is radix for
%   encoding variable tuple into lit/4 Code.
% Python fact detail: max_vars(Max) comes from args.max_variables; Max is count of available generated variables V0..V(Max-1).
#defined max_vars/1.

% Rule: detect duplicate normal predicate literals.
% Section0/Slot0 and Section1/Slot1 are ordered by section_order and Slot.
% Pred/Arity must match. same_vars/4 proves both literals use the same tuple.
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

% Rule: seed positional variable-code construction.
% Section/Slot/Mode identifies a selected literal. Arg position starts at 0 and
% Code starts at 0 before any argument variable has been folded in.
code_prefix(Section,Slot,Mode,0,0):-
    selected(Section,Slot,Mode).

% Rule: append one variable id to the positional code.
% Arg is the next argument index to encode. Code is the prefix value before Arg.
% NextArg is Arg+1. Base is max_vars. Var is the variable at Arg. NextCode is
% Code in base Base with Var appended as the least significant new digit.
code_prefix(Section,Slot,Mode,NextArg,NextCode):-
    code_prefix(Section,Slot,Mode,Arg,Code),
    mode(Section,Mode,_,Arity,_),
    Arg < Arity,
    NextArg = Arg + 1,
    max_vars(Base),
    var_at(Section,Slot,Arg,Var),
    NextCode = (Code * Base) + Var.

% Rule: emit one shown literal atom after all arguments are encoded.
% Section is head/body. Slot is occupied slot id. Mode is selected mode id.
% Code is the base-max_vars encoding of the full variable tuple. Python decodes
% Code back into the tuple using the mode arity and max_vars.
lit(Section,Slot,Mode,Code):-
    selected(Section,Slot,Mode),
    mode(Section,Mode,_,Arity,_),
    code_prefix(Section,Slot,Mode,Arity,Code).

% Output directive: expose only lit/4 in answer sets.
% All helper atoms remain internal to clingo. Python reads lit/4 symbols to
% reconstruct ReifiedClause instances.
#show lit/4.
