% Count uses of declarations, not just concrete mode variants.
% A shared recall group uses its tightest cap. Condition recalls are shared
% across every attachment in the clause, including head attachments.

#defined mode_condition_usage/3.
#defined condition_group_recall/2.
#defined recall_group/2.

selected_condition_group_count(Group, Count) :-
    condition_group_recall(Group, _),
    Count = #sum {
        Uses, Section, Slot, Mode :
        selected(Section, Slot, Mode),
        mode_condition_usage(Mode, Group, Uses)
    }.

:- selected_condition_group_count(Group, Count),
    condition_group_recall(Group, Recall),
    Count > Recall.

group_recall(Group, Recall) :-
    recall_group(_, Group),
    Recall = #min{ModeRecall : recall_group(Mode, Group), mode(_, Mode, _, _, ModeRecall)}.

selected_count(Group, Count) :-
    group_recall(Group, Recall),
    Count = #count{Section, Slot, Mode : selected(Section, Slot, Mode), recall_group(Mode, Group)}.

:- selected_count(Group, Count), group_recall(Group, Recall), Count > Recall.
