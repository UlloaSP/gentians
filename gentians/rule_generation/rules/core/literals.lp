% Normal literal classification.
%
% This file classifies selected normal predicate literals and gives pruning
% modules polarity-specific aliases. Operators, arithmetic, and aggregates are
% intentionally excluded from normal_literal/5.
%
% Shared atom shapes used here:
% - mode(Section,Mode,Pred,Arity,Recall): Python fact. Pred is predicate id and
%   Arity is predicate arity for normal modes.
% - normal_mode(Mode): Python fact. Mode renders as a normal predicate atom.
% - positive_mode(Mode): Python fact. Mode renders without default negation.
% - negative_mode(Mode): Python fact. Mode renders with "not".
% - selected(Section,Slot,Mode): defined in core/slots.lp.

% Python fact contract:
% - mode(Section,Mode,Pred,Arity,Recall): emitted by Python for every mode.
%   Pred/Arity identify rendered normal predicate literals.
% - normal_mode(Mode): emitted by Python when Mode renders as predicate atom.
% - positive_mode(Mode): emitted by Python when Mode renders without "not".
% - negative_mode(Mode): emitted by Python when Mode renders with default
%   negation in the body.
% Python fact detail: mode(Section,Mode,Pred,Arity,Recall) is emitted per hypothesis mode; Section=head/body, Mode=id, Pred=predicate id for normal modes, Arity=argument count, Recall=mode cap.
#defined mode/5.
% Python fact detail: normal_mode(Mode) marks modes rendered as normal predicate atoms.
#defined normal_mode/1.
% Python fact detail: positive_mode(Mode) marks modes rendered without default negation.
#defined positive_mode/1.
% Python fact detail: negative_mode(Mode) marks modes rendered with default negation in body.
#defined negative_mode/1.

% Rule: selected normal literal with predicate identity.
% Section is head/body. Slot is occupied slot id. Mode is selected mode id.
% Pred is the stable predicate id assigned by Python. Arity is predicate arity.
normal_literal(Section,Slot,Mode,Pred,Arity):-
    selected(Section,Slot,Mode),
    normal_mode(Mode),
    mode(Section,Mode,Pred,Arity,_).

% Rule: selected positive normal literal.
% Same arguments as normal_literal/5. positive_mode(Mode) means the rendered
% literal is Pred(...) rather than not Pred(...).
positive_normal_literal(Section,Slot,Mode,Pred,Arity):-
    normal_literal(Section,Slot,Mode,Pred,Arity),
    positive_mode(Mode).

% Rule: selected negative normal literal.
% Same arguments as normal_literal/5. negative_mode(Mode) means the rendered
% literal is default-negated in the body.
negative_normal_literal(Section,Slot,Mode,Pred,Arity):-
    normal_literal(Section,Slot,Mode,Pred,Arity),
    negative_mode(Mode).

% Rule: convenience alias for positive body predicate literals.
% Slot is body slot id. Mode is selected positive normal body mode. Pred/Arity
% identify the predicate.
positive_body_literal(Slot,Mode,Pred,Arity):-
    positive_normal_literal(body,Slot,Mode,Pred,Arity).

% Rule: convenience alias for negative body predicate literals.
% Slot is body slot id. Mode is selected negative normal body mode. Pred/Arity
% identify the predicate.
negative_body_literal(Slot,Mode,Pred,Arity):-
    negative_normal_literal(body,Slot,Mode,Pred,Arity).

% Rule: convenience alias for head predicate literals.
% Heads are positive normal literals only. Slot is head slot id. Mode, Pred, and
% Arity identify the selected head literal.
head_literal(Slot,Mode,Pred,Arity):-
    positive_normal_literal(head,Slot,Mode,Pred,Arity).
