% Count uses of declarations, not just concrete mode variants.
% A shared recall group uses its tightest cap. Condition recalls are shared
% across every attachment in the clause, including head attachments.


% DEFINITION, local helper. selected_condition_group_count(Group, Count): how
% many times the clause attaches conditions of one condition declaration.
%   Group  id of a condition declaration (#modec) with a recall cap.
%   Count  total uses of that declaration over all selected modes, in head and
%          body. A mode that attaches it twice contributes 2.
% Used only by the constraint below.
selected_condition_group_count(Group, Count) :-
    condition_group_recall(Group, _),
    Count = #sum {
        Uses, Section, Slot, Mode :
        selected(Section, Slot, Mode),
        mode_condition_usage(Mode, Group, Uses)
    }.

% CONSTRAINT. A condition declaration may not be attached more often than its
% recall.
%   Group   the condition declaration.
%   Count   its uses in the clause.
%   Recall  its cap (an unlimited recall is replaced by max_body).
% With #modec(1,node(var(node,any))):
%   pruned: :- p(V0) : node(V0); q(V1) : node(V1).    node attached twice
%   kept:   :- r(V0), p(V0) : node(V0).
:- selected_condition_group_count(Group, Count),
    condition_group_recall(Group, Recall),
    Count > Recall.

% DEFINITION, reusable. group_recall(Group, Recall): the recall cap of one
% mode declaration.
%   Group   id shared by every mode expanded from the same declaration (one
%           declaration can expand into several concrete modes).
%   Recall  the smallest mode_recall among those modes.
% Shared by selected_count and the constraint below, and by
% pruning/redundancy/comparisons.lp, which asks whether a "<" declaration
% still has room.
group_recall(Group, Recall) :-
    recall_group(_, Group),
    Recall = #min{ModeRecall : recall_group(Mode, Group), mode_recall(Mode, ModeRecall)}.

% DEFINITION, reusable. selected_count(Group, Count): how many literals of one
% mode declaration the clause selects.
%   Group  id of the declaration's recall group.
%   Count  number of selected slots, in head and body, whose mode belongs to
%          the group; 0 when none is selected.
% Shared by the constraint below and pruning/redundancy/comparisons.lp.
selected_count(Group, Count) :-
    group_recall(Group, Recall),
    Count = #count{Section, Slot, Mode : selected(Section, Slot, Mode), recall_group(Mode, Group)}.

% CONSTRAINT. A mode declaration may not be used more often than its recall.
%   Group   the declaration's recall group.
%   Count   its selected literals.
%   Recall  its cap.
% With #modeb(1,red(var(node,any))) and #modeb(2,edge(var(node,any),var(node,any))):
%   pruned: :- red(V0), red(V1), edge(V0,V1).        red used twice
%   kept:   :- red(V0), edge(V0,V1), edge(V1,V2).    edge twice is within 2
:- selected_count(Group, Count), group_recall(Group, Recall), Count > Recall.
