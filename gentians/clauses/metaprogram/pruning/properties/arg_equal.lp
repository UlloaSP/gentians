% Closed-world argument equality property.
%
% Python emits arg_equal_pred(Pred, Arg0, Arg1) when every true tuple of predicate
% Pred has equal values at argument positions Arg0 and Arg1. The enumerator
% chooses identical variable ids at these positions of positive literals, which
% can only be true for equal values. A negated literal with distinct ids is not
% equivalent: not same(X,Y) holds for every X != Y.
%
% One variable id is only possible where the template allows it. Two positions
% with different declared types (legality/typing.lp) or different labels
% (legality/labels.lp) can never share a variable, so there the atom keeps two
% ids and states the equality of their values by itself. Without this
% exception such a predicate could not appear in any clause.


% DEFINITION, local helper. arg_equal_unshareable(Mode, Arg0, Arg1): the two
% equal-valued argument positions of this atom template cannot hold one
% variable.
%   Mode        id of a template whose atom has the arg_equal property.
%   Arg0, Arg1  the two argument positions proved equal.
% Used only, negated, by the first constraint below.
% Case 1: the positions declare different nominal types.
arg_equal_unshareable(Mode, Arg0, Arg1) :-
    mode_atom(Mode, Pred, _),
    arg_equal_pred(Pred, Arg0, Arg1),
    mode_arg_type(Mode, Arg0, Type0),
    mode_arg_type(Mode, Arg1, Type1),
    Type0 != Type1.

% DEFINITION, local helper. Same predicate. Case 2: the positions carry
% different labels, which must name different variables.
arg_equal_unshareable(Mode, Arg0, Arg1) :-
    mode_atom(Mode, Pred, _),
    arg_equal_pred(Pred, Arg0, Arg1),
    mode_arg_label(Mode, Arg0, Label0),
    mode_arg_label(Mode, Arg1, Label1),
    Label0 != Label1.

% CONSTRAINT. A positive body atom must write the same variable id at two
% argument positions that always hold equal values, when its template lets
% them share a variable. With two ids the atom would force them equal, which
% the enumerator expresses with one id.
%   Slot, Mode  body slot and template of the positive atom.
%   Pred        its predicate.
%   Arg0, Arg1  two argument positions proved equal.
%   Var0, Var1  the two different variable ids found there.
% With arg_equal_pred(same,0,1):
%   pruned: h(V0) :- same(V0,V1).
%   kept:   h(V0) :- same(V0,V0).
%   kept:   h(V0) :- d(V0), d(V1), not same(V0,V1).   negation is not covered
%   kept:   :- same(V0,V1), a(V0).    when same is declared
%           same(var(a,any),var(b,any)): same(V0,V0) would mix two types
:- positive_body_literal(Slot, Mode, Pred, _),
    arg_equal_pred(Pred, Arg0, Arg1),
    not arg_equal_unshareable(Mode, Arg0, Arg1),
    var_at(body, Slot, Arg0, Var0),
    var_at(body, Slot, Arg1, Var1),
    Var0 != Var1.

% DEFINITION, local helper. arg_equal_condition_unshareable(Mode, Condition,
% LocalArg0, LocalArg1): the same obstacle for one condition atom of an
% aggregate template.
%   Mode                  id of an aggregate template of the single-element
%                         subset.
%   Condition             index of a condition whose atom has the property.
%   LocalArg0, LocalArg1  the two argument positions of that atom proved
%                         equal; their types and labels are read at the
%                         flattened positions they map to.
% Used only, negated, by the second constraint below.
% Case 1: different nominal types.
arg_equal_condition_unshareable(Mode, Condition, LocalArg0, LocalArg1) :-
    aggregate_condition_atom(Mode, Condition, Pred, _),
    arg_equal_pred(Pred, LocalArg0, LocalArg1),
    mode_aggregate_condition_arg(Mode, Condition, LocalArg0, Position0),
    mode_aggregate_condition_arg(Mode, Condition, LocalArg1, Position1),
    mode_arg_type(Mode, Position0, Type0),
    mode_arg_type(Mode, Position1, Type1),
    Type0 != Type1.

% DEFINITION, local helper. Same predicate. Case 2: different labels.
arg_equal_condition_unshareable(Mode, Condition, LocalArg0, LocalArg1) :-
    aggregate_condition_atom(Mode, Condition, Pred, _),
    arg_equal_pred(Pred, LocalArg0, LocalArg1),
    mode_aggregate_condition_arg(Mode, Condition, LocalArg0, Position0),
    mode_aggregate_condition_arg(Mode, Condition, LocalArg1, Position1),
    mode_arg_label(Mode, Position0, Label0),
    mode_arg_label(Mode, Position1, Label1),
    Label0 != Label1.

% CONSTRAINT. The same check inside an aggregate: a condition atom must write
% one variable id at two argument positions that always hold equal values,
% when its template lets them share a variable.
%   Slot                  body slot of an aggregate of the single-element
%                         subset.
%   Condition, Pred       a condition occurrence and its predicate.
%   LocalArg0, LocalArg1  two argument positions of Pred proved equal.
%   Var0, Var1            the two different variable ids found there.
% With arg_equal_pred(same,0,1):
%   pruned: #count{V0,V1 : same(V0,V1)} = V2
%   kept:   #count{V0 : same(V0,V0)} = V1     by this constraint; the policy in
%           pruning/policies/aggregates.lp then rejects the repeated V0
:- selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Pred, _),
    arg_equal_pred(Pred, LocalArg0, LocalArg1),
    not arg_equal_condition_unshareable(Mode, Condition, LocalArg0, LocalArg1),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg0, Var0),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg1, Var1),
    Var0 != Var1.
