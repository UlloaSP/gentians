% Optional and cross-module predicate declarations for clause generation.
%
% Clingo's #defined directive only declares that a predicate belongs to the
% program vocabulary. It neither creates facts nor gives the predicate a
% closed-world meaning beyond normal ASP semantics. A declared predicate can
% therefore be empty for a particular task. Python emits most relations below;
% a few are views defined by another metaprogram module. Keeping the declarations
% here makes the Python-to-ASP contract visible in one place and prevents each
% consumer from restating part of that contract.
%
% Identifier conventions used throughout this file:
%   Mode       integer id of one compiled language-bias template.
%   Predicate  integer id of a signed predicate signature; p/n and -p/n differ.
%   Section    head or body.
%   Slot       occurrence position inside a section of the candidate clause.
%   Position   zero-based variable-placeholder position in a mode. For a plain
%              atom (only variables and constants) it is the source argument
%              index, so property facts line up with it; otherwise it is the
%              flattened placeholder index and constants occupy none.
%   Argument   zero-based source-level predicate argument position.
%   Variable   integer id rendered as V0, V1, ...; it is not a ground value.
%   Form       id shared by all elements of one compound head declaration.
%   Condition  zero-based occurrence id inside a conditional or aggregate.
%
% Comment conventions used by every other module. Each rule, choice and
% constraint carries a comment of one of these kinds directly above it:
%   DEFINITION  a rule that derives a view. "reusable" names the modules that
%               consume it and why it is shared; "local helper" is used only
%               inside its own file; "property bridge" derives a weaker
%               property so that the file owning that property prunes for it.
%               Every argument of the head is listed.
%   CHOICE      a generator: it opens the alternatives that models differ in.
%   CONSTRAINT  defines nothing and only removes models. "pruned" and "kept"
%               show rendered candidate clauses (one stable model each) or
%               body fragments. "kept" means that this constraint does not
%               reject the clause; another independent constraint still can.
%               "(policy)" marks a restriction of the enumerator that is not
%               an ASP impossibility or redundancy.
%
% Generation limits and feature switches.

% max_vars(Max): the candidate may use variable ids 0 through Max-1.
#defined max_vars/1.

% max_body(Max): the body exposes slots 0 through Max-1.
#defined max_body/1.

% enumerate_by_size: incremental generation requests models grouped by the
% total number of selected body literals and attached conditions.
#defined enumerate_by_size/0.

% prune_optional_constraints: static task analysis proved that a perfect
% hypothesis for this positive-only task needs a learned headed clause.
#defined prune_optional_constraints/0.

% positive_arg(Pred, Arg) / nonnegative_arg(Pred, Arg): every value closed
% predicate Pred takes at source argument Arg, in every model of every context,
% is an integer > 0 or >= 0. They are evidence for sound numeric consequences of
% variables a positive body literal grounds there.
#defined positive_arg/2.
#defined nonnegative_arg/2.

% Core mode identity and shape.

% mode_section(Mode, Section): where this template may occur.
#defined mode_section/2.

% mode_kind(Mode, Kind): syntactic family, one of normal, conditional,
% comparison, arithmetic, aggregate, head_aggregate or boolean.
#defined mode_kind/2.

% plain_disjunctive_head_mode(Mode): Mode is an unconditional atom in a normal
% or disjunctive head. Negated disjuncts, choice/cardinality and conditioned
% heads are absent.
#defined plain_disjunctive_head_mode/1.

% mode_recall(Mode, Recall): effective maximum occurrences of this mode after
% replacing an unlimited source recall with the finite structural bound.
#defined mode_recall/2.

% recall_group(Mode, Group): modes expanded from the same declaration share a
% recall budget identified by Group.
#defined recall_group/2.

% mode_shape(Mode, Shape): id of the complete recursive term shape used when
% testing whether two selected occurrences have identical term structure.
#defined mode_shape/2.

% mode_atom(Mode, Predicate, Arity): predicate signature represented by a
% normal mode, the conclusion of a conditional mode, or an element of a head
% aggregate. Operators and body aggregates intentionally have no mode_atom fact.
#defined mode_atom/3.

% negative_mode(Mode): the atom, conditional conclusion, or head aggregate
% element is under default negation and cannot produce globally bound variables.
#defined negative_mode/1.

% double_negative_mode(Mode): the negated form is `not not`; it is also a
% negative_mode.
#defined double_negative_mode/1.

% conditional_mode(Mode): cross-module view derived from
% mode_kind(Mode, conditional).
#defined conditional_mode/1.

% Argument schema. Position follows the convention above: a source argument
% index for plain atoms, a flattened binding otherwise. A fixed term occupies no
% Position and a structured term can occupy several.

% mode_variable_arg(Mode, Position): Position is a variable placeholder of Mode.
#defined mode_variable_arg/2.

% mode_arg_type(Mode, Position, Type): nominal type required at Position.
% Positions declared as any deliberately have no fact.
#defined mode_arg_type/3.

% mode_arg_direction(Mode, Position, Direction): input, output or any.
% Every variable placeholder with a declared direction has one fact.
#defined mode_arg_direction/3.

% Binding alternatives of a positive body atom whose placeholders do not all
% ground their variable: a pool expands into alternatives, and a placeholder
% inside non-invertible arithmetic (q(X+Y), q(|X|), q(X/2)) grounds nothing.
% A variable is grounding-safe through that atom only if every alternative
% lists a position holding it. Positions refer to flattened placeholders.
#defined mode_pool_alternative/2.
#defined mode_pool_alternative_arg/3.

% A positive condition binds a local variable only if every binding
% alternative contains it (pools and non-invertible arithmetic). Scope and Element identify its local region.
#defined local_pool_condition_arg/5.
#defined local_pool_alternative/5.
#defined local_pool_alternative_arg/6.

% mode_arg_label(Mode, Position, Label): source label attached to this mode
% position, used to preserve declared argument identity.
#defined mode_arg_label/3.

% relation_output_mode(Mode): a comparison template has at least one output
% binding and is therefore treated as a relation that can produce a value.
#defined relation_output_mode/1.

% Compound heads and labels.

% head_form_member(Form, Slot, Mode): Form contains Mode at head Slot. Selecting
% a form selects all of its members; the members are not independent choices.
#defined head_form_member/3.

% composite_head_form(Form): Form is a choice, cardinality or function aggregate
% head. Its elements form one linked component.
#defined composite_head_form/1.

% head_arg_label(Form, Mode, Position, Label): labelled position inside one
% compound head form; labels with the same name must denote one variable.
#defined head_arg_label/4.

% Conditional-literal schema.

% conditional_main_arg(Mode, Position): Position belongs to the conclusion of
% the conditional literal rather than to an attached condition.
#defined conditional_main_arg/2.

% conditional_condition(Mode, Condition, Predicate, Polarity): Condition is an
% atom occurrence with its signed predicate id and positive/negative polarity.
% Comparison conditions have no predicate signature and omit this fact.
#defined conditional_condition/4.

% conditional_condition_arg(Mode, Condition, Argument, Position): source
% Argument of one condition occurrence maps to flattened Position in Mode.
#defined conditional_condition_arg/4.

% conditional_condition_variant(Mode, Condition, Variant): canonical id of the
% complete condition syntax, used only to order or deduplicate equal variants.
#defined conditional_condition_variant/3.

% conditional_shorter_mode(Mode, Condition): the language also contains Mode's
% template without condition Condition, so a repeated condition is removable.
#defined conditional_shorter_mode/2.

% Theta reduction (pruning/redundancy/theta.lp). A section holding repeatable
% movable literals gets exactly one of two encodings. theta_sigma_section with
% theta_sigma(Id) and theta_sigma_offset(Id, Section, Slot, Offset) enumerate
% every offset combination: the literal in Slot maps to the first slot of its
% mode group plus Offset. theta_saturated_section selects the disjunctive
% saturation instead, used only when those combinations would be too many.
#defined theta_sigma_section/1.
#defined theta_sigma/1.
#defined theta_sigma_offset/4.
#defined theta_saturated_section/1.

% mode_condition_count(Mode, Count): number of conditions attached to Mode.
#defined mode_condition_count/2.

% mode_condition_usage(Mode, Group, Count): Mode consumes Count occurrences from
% the recall budget of conditional declaration Group.
#defined mode_condition_usage/3.

% condition_group_recall(Group, Recall): maximum total uses of conditions
% expanded from the same conditional declaration group.
#defined condition_group_recall/2.

% Arithmetic schema and eligible operator families.

% mode_arithmetic_operand(Mode, Side, Position): left or right expression
% operand of a recognized three-placeholder arithmetic template.
#defined mode_arithmetic_operand/3.

% mode_arithmetic_result(Mode, Position): result placeholder of that template.
#defined mode_arithmetic_result/2.

% add_mode / mul_mode: Mode is a complete + or * template.
#defined add_mode/1.
#defined mul_mode/1.

% interchangeable_operands(Mode): the two operands of an arithmetic template or
% a simple binary comparison, or the two arguments of a binary atom of plain
% variables, have equal type, direction and label, so swapping them yields
% another template instance. Every orientation choice requires it: a swapped
% literal of a directed or typed template can be illegal.
#defined interchangeable_operands/1.

% div_mode / mod_mode: Mode is a complete / or modulo template. Operand order is
% significant; the flags enable their dedicated semantic views and checks.
#defined div_mode/1.
#defined mod_mode/1.

% abs_mode: Mode is a complete |Left-Right| template.
#defined abs_mode/1.

% Comparison schema.

% comparison_operator(Mode, Operator): Mode is a simple binary comparison whose
% sole operator is one of eq, neq, lt, gt, leq or geq. Complex comparison chains
% deliberately have no fact.
#defined comparison_operator/2.

% strict_comparison_args(Mode, LeftPosition, RightPosition): two adjacent plain
% variable terms of Mode are related by < or > at these flattened positions.
#defined strict_comparison_args/3.

% Aggregate schema. Condition ids preserve repeated occurrences of the same
% predicate; Position remains the flattened storage position of the mode.

% aggregate_shape(Mode, TupleArity, ConditionCount): source tuple width and
% number of condition occurrences of an aggregate template.
#defined aggregate_shape/3.

% aggregate_has_shorter_mode(Mode): the language bias also declares an aggregate
% of the same function and conditions with one fewer tuple term.
#defined aggregate_has_shorter_mode/1.

% count_aggregate_mode / sum_aggregate_mode: aggregate function of Mode.
#defined count_aggregate_mode/1.
#defined sum_aggregate_mode/1.

% mode_aggregate_tuple_arg(Mode, TuplePosition, Position): variable binding at a
% source tuple position maps to flattened Position.
#defined mode_aggregate_tuple_arg/3.

% aggregate_condition_atom(Mode, Condition, Predicate, Arity): identity and
% arity of one aggregate condition occurrence.
#defined aggregate_condition_atom/4.

% mode_aggregate_condition_arg(Mode, Condition, Argument, Position): one source
% argument of a condition occurrence maps to flattened Position.
#defined mode_aggregate_condition_arg/4.

% interchangeable_condition_args(Mode, Condition): the same guarantee for the
% two arguments of one binary condition atom of an aggregate template.
#defined interchangeable_condition_args/2.

% mode_aggregate_result_arg(Mode, Position): variable binding of the aggregate
% guard/result maps to flattened Position.
#defined mode_aggregate_result_arg/2.

% General aggregate elements have independent local variable scopes. Guard
% positions remain clause-global; only an equality output produces a binding.
#defined mode_aggregate_element_tuple_arg/4.
#defined aggregate_element_condition_atom/5.
#defined aggregate_element_atom/4.
#defined mode_aggregate_element_condition_arg/5.
#defined mode_aggregate_element_positive_arg/4.
#defined mode_aggregate_guard_arg/2.
#defined mode_aggregate_output_arg/2.

% Clingo-proved local comparison bindings and the inputs each proof needs.
#defined local_comparison_variant/6.
#defined local_comparison_input/6.
#defined local_comparison_output/6.

% Exact #modeh head aggregate elements and their positive local conditions.
#defined head_aggregate_element_arg/2.
#defined head_aggregate_condition_atom/3.
#defined head_aggregate_positive_condition_arg/3.
#defined head_guard_arg/2.

% Predicate invention and signed predicate identity.

% invented_pred(Predicate, Layer): Predicate is invented at dependency Layer;
% it may depend only on permitted background or earlier invented predicates.
#defined invented_pred/2.

% strong_complement_pred(Positive, Negative): ids for p/n and -p/n. This records
% strong negation, not default negation.
#defined strong_complement_pred/2.

% Unary properties proved by Clingo for closed predicates: predicates that no
% learned clause can define, directly or through the background. Each property
% holds in the background plus every example context separately. Every argument
% is a signed Predicate id. Absence means "not proved", not that the
% mathematical property is false.

% symmetric_pred: p(X,Y) entails p(Y,X).
#defined symmetric_pred/1.
% asymmetric_pred: p(X,Y) excludes p(Y,X).
#defined asymmetric_pred/1.
% antisymmetric_pred: p(X,Y) and p(Y,X) force X=Y.
#defined antisymmetric_pred/1.
% acyclic_pred: no directed cycle is allowed in the relation.
#defined acyclic_pred/1.
% reflexive_pred: p(X,X) holds for every X in the field of p (domain field(p)).
#defined reflexive_pred/1.
% strict_order_pred: the relation is an irreflexive transitive order.
#defined strict_order_pred/1.
% total_order_pred: the relation is a total order on its field (domain field(p)).
#defined total_order_pred/1.
% transitive_pred: p(X,Y) and p(Y,Z) entail p(X,Z).
#defined transitive_pred/1.
% universal_pred: p contains every tuple of the product of its argument values
% (domain universal(p)).
#defined universal_pred/1.
% empty_pred: p has no tuples in the analyzed closed-world relation.
#defined empty_pred/1.

% Relations between predicates proved from background rules or ground evidence.

% inverse_pred(Left, Right): Left(X,Y) is equivalent to Right(Y,X).
#defined inverse_pred/2.

% implies_pred(Source, Target): every Source tuple is a Target tuple.
#defined implies_pred/2.

% equivalent_pred(Left, Right): both predicates contain the same tuples.
#defined equivalent_pred/2.

% mutex_pred(Left, Right): the predicates cannot hold for the same full tuple.
#defined mutex_pred/2.

% complement_pred(Left, Right): the predicates are disjoint and their union is
% the product of its argument values (domain complement(Left, Right)).
#defined complement_pred/2.

% partition_pred(Group, Predicate): predicates sharing Group are pairwise
% disjoint and their union is the product of its argument values (domain
% partition(Group)).
#defined partition_pred/2.

% domain_cover(Domain, Position, Predicate, Argument): every value of the
% closed Predicate at source Argument lies inside Position of Domain, one of
% field(p), universal(p), complement(p,q) or partition(Group). Domain-relative
% pruning applies only to variables bound at such arguments.
#defined domain_cover/4.

% disjoint_arg(Left, LeftArg, Right, RightArg): the projections at the specified
% source argument positions have disjoint observed values.
#defined disjoint_arg/4.

% tuple_mutex_pred(Left, Right, Mapping): Left and Right are mutually exclusive
% after aligning a projection identified by Mapping.
#defined tuple_mutex_pred/3.

% tuple_mutex_arg(Mapping, RightArg, LeftArg): one argument alignment belonging
% to a tuple-mutex Mapping.
#defined tuple_mutex_arg/3.

% project_implies_pred(Source, Target, Projection): projecting Source according
% to Projection entails Target.
#defined project_implies_pred/3.

% project_arg(Projection, TargetArg, SourceArg): argument correspondence for one
% projected implication.
#defined project_arg/3.

% Properties of argument positions.

% arg_equal_pred(Predicate, LeftArg, RightArg): the two positions are always
% equal in the analyzed relation.
#defined arg_equal_pred/3.

% arg_distinct_pred(Predicate, LeftArg, RightArg): the two positions are always
% different in the analyzed relation.
#defined arg_distinct_pred/3.

% functional_pred(Predicate, InputArg, OutputArg): one input position
% functionally determines one output position.
#defined functional_pred/3.

% functional_set_pred(Predicate, Dependency, OutputArg): Dependency identifies
% a set of input positions that jointly determines OutputArg.
#defined functional_set_pred/3.

% functional_set_arg(Dependency, InputArg): one determining position of a
% functional-set Dependency.
#defined functional_set_arg/2.

% key_pred(Predicate, Key): Key identifies a set of positions that uniquely
% determines a tuple of Predicate.
#defined key_pred/2.

% key_arg(Key, Argument): one source argument position belonging to Key.
#defined key_arg/2.

% cardinality_upper_pred(Predicate, Upper): proved upper bound on the number of
% tuples in Predicate over the analyzed task domain.
#defined cardinality_upper_pred/2.
