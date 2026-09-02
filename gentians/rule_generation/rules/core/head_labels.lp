% Optional labels inside one complete head mode constrain variable identity.

#defined head_arg_label/4.
#defined default_variable_identity/0.

head_label_var(Form,Label,Var):-
    selected_head_form(Form),
    head_arg_label(Form,Mode,Arg,Label),
    selected(head,Slot,Mode),
    var_at(head,Slot,Arg,Var).

:- default_variable_identity,
    head_label_var(Form,Label,Left),
    head_label_var(Form,Label,Right),
    Left != Right.

:- default_variable_identity,
    head_label_var(Form,LeftLabel,Var),
    head_label_var(Form,RightLabel,Var),
    LeftLabel < RightLabel.
