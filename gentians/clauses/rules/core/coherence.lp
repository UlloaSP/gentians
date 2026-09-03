% Strong-negation coherence pruning.
%
% Python assigns different predicate ids to p/n and -p/n and emits one
% strong_complement_pred/2 fact for every declared pair. Strong complements
% are mutex: requiring both positively is impossible, while a positive atom
% makes default negation of its strong complement redundant. The shared mutex
% rules perform both prunings and leave two default-negated atoms untouched.

#defined strong_complement_pred/2.

mutex_pred(Pred0,Pred1):- strong_complement_pred(Pred0,Pred1).
