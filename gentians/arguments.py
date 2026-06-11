import argparse
import sys

program_description = "GENTIANS: GENeTic algorithm for Inductive learning of ANswer Set programs."

version = "1.0.1"

class Arguments:
    def __init__(self, args : argparse.Namespace) -> None:
        self.filename : str = args.file
        self.verbosity : int = args.verbosity
        self.max_variables : int = args.variables
        self.max_depth : int = args.depth
        self.prob_increase : float = args.prob_increase
        self.disjunctive_head_length : int = args.disjunctive_head
        self.clauses_to_sample : int = args.samples
        self.unbalanced_aggregates : bool = args.unbalanced_agg
        self.max_as : int = args.max_as
        self.clauses_per_individual : int = args.clauses
        self.iterations : int = args.iterations
        self.population_size : int = args.pop_size
        self.iterations_genetic : int = args.iterations_genetic
        self.mutation_probability : float = args.mutation_probability
        self.example : str = args.example
        self.cr : bool = args.cr
        self.aggregates : 'list[str]' = args.aggregates
        self.comparison_operators : 'list[str]' = args.comparison
        self.arithmetic_operators : 'list[str]' = args.arithm
        self.predicate_invention : int = args.invention
        self.automatic_language_bias : int = args.alb
        self.profile : bool = args.profile
        self.profile_output : str = args.profile_output
        self.profile_dataset : str = args.profile_dataset
        self.profile_run : int = args.profile_run
        self.seed : int = args.seed
        self.version : bool = args.version
        print(args)

def parse_arguments() -> 'Arguments':
    '''
    Parses command line arguments.
    '''
    command_parser = argparse.ArgumentParser(description=program_description)
    command_parser.add_argument(
        "-f",
        "--file",
        help="File containing the task.",
        type=str,
        default=None
    )
    command_parser.add_argument(
        "-v",
        "--verbosity",
        help="Verbosity",
        type=int,
        choices=range(0,3),
        default=0
    )
    command_parser.add_argument(
        "-vars",
        "--variables",
        help="Max number of variables to consider in a rule",
        type=int,
        default=3
    )
    command_parser.add_argument(
        "-d",
        "--depth",
        help="Max number of literals in rules",
        type=int,
        default=3
    )
    command_parser.add_argument(
        "-pil",
        "--prob-increase",
        help="Probability to add one more literal in the current clause (used in sampling)",
        type=float,
        default=0.5
    )
    command_parser.add_argument(
        "-dh",
        "--disjunctive-head",
        help="Max atoms in head",
        type=int,
        default=1
    )
    command_parser.add_argument(
        "-s",
        "--samples",
        help="Number of clauses to sample",
        type=int,
        default=1000
    )
    command_parser.add_argument(
        "-ua",
        "--unbalanced-agg",
        help="Enable unbalanced aggregates",
        action="store_true"
    )
    command_parser.add_argument(
        "--max_as",
        help="Max number of answer sets to generate",
        type=int,
        default=5000
    )
    command_parser.add_argument(
        "-c",
        "--clauses",
        help="Max clauses to consider in a program",
        type=int,
        default=6
    )
    command_parser.add_argument(
        "-it",
        "--iterations",
        help="Max number of sample and genetic iterations",
        type=int,
        default=100
    )
    command_parser.add_argument(
        "-p",
        "--pop-size",
        help="Population size",
        type=int,
        default=50
    )
    command_parser.add_argument(
        "-itg",
        "--iterations-genetic",
        help="Number of iterations for the genetic algorithm",
        type=int,
        default=2000
    )
    command_parser.add_argument(
        "-mp",
        "--mutation-probability",
        help="Mutation probability",
        type=float,
        default=0.2
    )
    command_parser.add_argument(
        "-e",
        "--example",
        help="Load a predefined example",
        choices=[
            "coin", 
            "even_odd",
            "animals_bird",
            "coloring",
            "adjacent_to_red",
            "grandparent",
            "4queens",
            "5queens", 
            "clique", 
            "sudoku",
            # "euclid",
            # "dummy", 
            "subset_sum",
            "subset_sum_double",
            "subset_sum_double_and_sum",
            "subset_sum_double_and_prod",
            "subset_sum_triple",
            "knapsack",
            "hamming_0", 
            "hamming_1", 
            # "harder_hamming_0",
            # "harder_hamming_1",
            "magic_square_no_diag", 
            "latin_square", 
            "set_partition_sum",
            "set_partition_sum_and_cardinality", 
            "set_partition_sum_cardinality_and_square",
            "set_partition_sum_new", 
            "set_partition_sum_and_cardinality_new",
            "user_defined"
        ],
        default=None
    )
    command_parser.add_argument(
        "--comparison",
        help="Enables the usage of comparison \
        predicates: less than (<) with lt, less equal (<=) with leq, \
        greater than (>) with gt, greater equal (>=) with geq \
        equal (==) with eq and different (!=) with neq.\
        Example: --comparison lt gt eq diff",
        nargs='+',
        required=False,
        choices=["lt","leq","gt","geq","eq","neq"]
    )
    command_parser.add_argument(
        "--arithm",
        help="Enables the usage of arithmetic \
        predicates: add (+), sub(-), mul(*), div(/), and abs (||). Example: \
        --arithm add sub mul div abs",
        nargs='+',
        required=False,
        choices=["add","sub","mul","div","abs"]
    )
    command_parser.add_argument(
        "--aggregates",
        help="Enable aggregates. Example:\
        --aggregates sum(a/1) count (a/1). Specify the atom to aggregate.", 
        nargs='+',
        required=False
    )
    command_parser.add_argument(
        "--cr",
        help="Enables the generation of choice rules.",
        action="store_true"
    )
    command_parser.add_argument(
        "--invention",
        help="Enables predicate invention with n predicates. Example --invention=1",
        type=int,
        default=0
    )
    command_parser.add_argument(
        "-alb",
        help="Automatic language bias discovery with the specified recall.",
        type=int,
        default=0
    )
    command_parser.add_argument(
        "--profile",
        help="Enables profiling", 
        default=False,
        action="store_true"
    )
    command_parser.add_argument(
        "--profile-output",
        help="Writes detailed GENTIANS timing profile JSON to this path.",
        type=str,
        default=None
    )
    command_parser.add_argument(
        "--profile-dataset",
        help="Dataset label stored in --profile-output.",
        type=str,
        default=None
    )
    command_parser.add_argument(
        "--profile-run",
        help="Run number stored in --profile-output.",
        type=int,
        default=0
    )
    command_parser.add_argument(
        "--seed",
        help="Random seed for reproducible runs.",
        type=int,
        default=None
    )
    command_parser.add_argument(
        "--version",
        help="Prints the program version and exits", 
        action="store_true"
    )
    
    return Arguments(command_parser.parse_args())
