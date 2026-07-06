% Mode recall constraints.
%
% This file enforces how many times each language-bias recall group may appear
% in one generated clause.  Multiple concrete modes may share one group, for
% example aggregate variants created from the same declaration.
%
% Shared atom shapes used here:
% - recall_group(Mode,Group): Python fact. Mode is a generator mode id; Group
%   is the recall bucket id used for counting.
% - group_recall(Group,Recall): Python fact. Recall is the maximum number of
%   selected literals whose mode belongs to Group.
% - selected(Section,Slot,Mode): defined in core/slots.lp. Section is head/body;
%   Slot is occupied slot id; Mode is selected generator mode id.

% Python fact contract:
% - recall_group(Mode,Group): emitted by Python for every mode. Mode is mode id;
%   Group is shared recall bucket id, used when variants come from same bias.
% - group_recall(Group,Recall): emitted by Python after grouping modes. Recall
%   is max selections allowed from that Group in one clause.
% Python fact detail: recall_group(Mode,Group) maps a mode id to the recall bucket counted for language-bias recall.
#defined recall_group/2.
% Python fact detail: group_recall(Group,Recall) gives max selected literals allowed from recall bucket Group.
#defined group_recall/2.

% Rule: count selected literals per recall group.
% Group is each group declared by group_recall. Count counts triples
% Section/Slot/Mode whose selected Mode maps to Group via recall_group.
selected_count(Group,Count):-
    group_recall(Group,_),
    Count = #count{Section,Slot,Mode : selected(Section,Slot,Mode), recall_group(Mode,Group)}.

% Constraint: reject clauses exceeding recall.
% Count is selected_count for Group. Recall is group_recall limit for Group.
:- selected_count(Group,Count), group_recall(Group,Recall), Count > Recall.
