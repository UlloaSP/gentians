% Labels constrain identity within a mode and across one complete head form.
% Equal labels share a variable; different labels must use different variables.


% DEFINITION, local helper. head_label_var(Form, Label, Var): inside the
% selected head form, a placeholder labelled Label holds Var.
%   Form   id of the selected compound head form.
%   Label  source label of the placeholder, such as x in var(node,input,x).
%   Var    variable id written at that placeholder, in any member of the form.
% Gathers labels across all members of one head, which no single mode can see.
% Used only by the first two constraints below.
head_label_var(Form, Label, Var) :-
    selected_head_form(Form),
    head_arg_label(Form, Mode, Arg, Label),
    selected(head, Slot, Mode),
    var_at(head, Slot, Arg, Var).

% DEFINITION, local helper. mode_label_var(Section, Slot, Label, Var): inside
% the literal at that slot, a placeholder labelled Label holds Var.
%   Section, Slot  the selected literal, in head or body.
%   Label          source label of one of its placeholders.
%   Var            variable id written there.
% Used only by the last two constraints below.
mode_label_var(Section, Slot, Label, Var) :-
    selected(Section, Slot, Mode),
    mode_arg_label(Mode, Arg, Label),
    var_at(Section, Slot, Arg, Var).

% CONSTRAINT. Within one head form, placeholders with the same label must hold
% the same variable.
%   Form, Label  the head form and the shared label.
%   Left, Right  the two variable ids found under that label.
% With #modeh(1,red(var(node,input,x));green(var(node,input,x))):
%   pruned: red(V0);green(V1) :- node(V0), node(V1).
%   kept:   red(V0);green(V0) :- node(V0).
:- head_label_var(Form, Label, Left),
    head_label_var(Form, Label, Right),
    Left != Right.

% CONSTRAINT. Within one head form, placeholders with different labels must
% hold different variables.
%   Form                   the head form.
%   LeftLabel, RightLabel  two distinct labels; "<" lists each pair once.
%   Var                    the variable id found under both.
% With #modeh(1,from(var(node,input,a));to(var(node,input,b))):
%   pruned: from(V0);to(V0) :- node(V0).
%   kept:   from(V0);to(V1) :- edge(V0,V1).
:- head_label_var(Form, LeftLabel, Var),
    head_label_var(Form, RightLabel, Var),
    LeftLabel < RightLabel.

% CONSTRAINT. Within one literal, placeholders with the same label must hold
% the same variable.
%   Section, Slot  the literal.
%   Label          the shared label.
%   Left, Right    the two variable ids found under that label.
% With #modeb(1,same(var(node,any,x),var(node,any,x))):
%   pruned: :- same(V0,V1).
%   kept:   :- same(V0,V0).
:- mode_label_var(Section, Slot, Label, Left),
    mode_label_var(Section, Slot, Label, Right),
    Left != Right.

% CONSTRAINT. Within one literal, placeholders with different labels must hold
% different variables.
%   Section, Slot          the literal.
%   LeftLabel, RightLabel  two distinct labels; "<" lists each pair once.
%   Var                    the variable id found under both.
% With #modeb(1,edge(var(node,any,a),var(node,any,b))):
%   pruned: :- edge(V0,V0).
%   kept:   :- edge(V0,V1).
:- mode_label_var(Section, Slot, LeftLabel, Var),
    mode_label_var(Section, Slot, RightLabel, Var),
    LeftLabel < RightLabel.
