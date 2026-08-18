% Mode recall constraints.
%
% This file enforces how many times each language-bias recall group may appear
% in one generated clause.  Multiple concrete modes may share one group, for
% example aggregate variants created from the same declaration.
%
% Shared atom shapes used here:
% - recall_group(Mode,Group): Python fact. Mode is a generator mode id; Group
%   is the recall bucket id used for counting.
% - group_recall(Group,Recall): derived atom. Recall is the maximum number of
%   selected literals whose mode belongs to Group.
% - mode(Section,Mode,Pred,Arity,Recall): Python fact carrying per-mode recall.
% - selected(Section,Slot,Mode): defined in core/slots.lp. Section is head/body;
%   Slot is occupied slot id; Mode is selected generator mode id.

% Python fact contract:
% - recall_group(Mode,Group): emitted by Python for every mode. Mode is mode id;
%   Group is shared recall bucket id, used when variants come from same bias.
% - mode(Section,Mode,Pred,Arity,Recall): emitted by Python for every mode.
%   This file derives group_recall/2 as the tightest recall in each Group.
% Python fact detail: recall_group(Mode,Group) maps a mode id to the recall bucket counted for language-bias recall.
#defined recall_group/2.

% Rule: derive tightest recall limit for each recall group.
% Group is a recall bucket id. Recall is the minimum per-mode recall among all
% modes mapped to Group. Python emits per-mode recall in mode/5, so this module
% owns the grouping logic.
group_recall(Group,Recall):-
    recall_group(_,Group),
    Recall = #min{ModeRecall : recall_group(Mode,Group), mode(_,Mode,_,_,ModeRecall)}.

% Rule: count selected literals per recall group.
selected_count(Group,Count):-
    group_recall(Group,Recall),
    Count = #count{Section,Slot,Mode : selected(Section,Slot,Mode), recall_group(Mode,Group)}.

% Constraint: reject clauses exceeding recall.
% Count is selected_count for Group. Recall is group_recall limit for Group.
:- selected_count(Group,Count), group_recall(Group,Recall), Count > Recall.
