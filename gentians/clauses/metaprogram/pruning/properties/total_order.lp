% Closed-world total order predicate property.
%
% Python emits total_order_pred(Pred) when binary predicate Pred behaves like a
% total order over its field (see domains.lp). A total order is reflexive,
% antisymmetric, and transitive; this file exports those base-property atoms and
% keeps only the totality-specific pruning, which needs both variables inside
% the field: not le(X,Y), not le(Y,X) is satisfiable for values outside it.


% DEFINITION, reusable property bridge. reflexive_pred(Pred): Pred(X,X) holds
% for every X of its field.
%   Pred  signed predicate id of a binary closed predicate proved a total
%         order.
% The self-pair checks are owned by pruning/properties/reflexive.lp.
reflexive_pred(Pred) :- total_order_pred(Pred).

% DEFINITION, reusable property bridge. antisymmetric_pred(Pred): Pred holds
% in both directions only for equal values.
%   Pred  as above.
% The reversed-pair check is owned by pruning/properties/antisymmetric.lp.
antisymmetric_pred(Pred) :- total_order_pred(Pred).

% DEFINITION, reusable property bridge. transitive_pred(Pred): Pred(X,Y) and
% Pred(Y,Z) entail Pred(X,Z).
%   Pred  as above.
% The shortcut checks are owned by pruning/properties/transitive.lp.
transitive_pred(Pred) :- total_order_pred(Pred).

% CONSTRAINT. A total order may not be denied in both directions for two
% variables that certainly lie in its field: one direction holds there, so
% the body could never be satisfied.
%   Slot0 < Slot1  body slots of "not Pred(Left,Right)" and
%                  "not Pred(Right,Left)".
%   Pred           a total order.
%   Left, Right    two different variable ids, each bound inside field(Pred)
%                  by a positive body atom.
% With le/2 a total order on its field:
%   pruned: :- le(V0,V2), le(V1,V2), not le(V0,V1), not le(V1,V0).
%   kept:   :- le(V0,V2), le(V1,V2), not le(V0,V1).
%   kept:   :- n(V0), n(V1), not le(V0,V1), not le(V1,V0).
%           when n can reach values outside the field
:- negative_body_literal(Slot0, _, Pred, 2),
    negative_body_literal(Slot1, _, Pred, 2),
    Slot0 < Slot1,
    total_order_pred(Pred),
    var_at(body, Slot0, 0, Left),
    var_at(body, Slot0, 1, Right),
    Left != Right,
    var_at(body, Slot1, 0, Right),
    var_at(body, Slot1, 1, Left),
    covered_var(field(Pred), 0, Left),
    covered_var(field(Pred), 0, Right).
