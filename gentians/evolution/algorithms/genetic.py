import time

from ...arguments import Arguments
from ..individual import Individual
from ..types import (
    CrossoverFn,
    FitnessFn,
    MutationFn,
    PickTwoFn,
    PopulationInitializerFn,
    ReplacementFn,
    SelectionFn,
)
from ...rule_generation.placed_clause import PlacedClause
from ...rule_generation.program import Program
from ...timing import phase, profile_phase, record_ga_generation


class Strategy:
    def __init__(
        self,
        placed_list: "list[PlacedClause]",
        # background : 'list[str]',
        # positive_examples : 'list[list[str]]',
        # negative_examples : 'list[list[str]]',
        program: Program,
        args: Arguments,
        evaluate_score: FitnessFn,
        population_initializer: PopulationInitializerFn,
        selection: SelectionFn,
        pick_two: PickTwoFn,
        crossover: CrossoverFn,
        mutation: MutationFn,
        replacement: ReplacementFn,
    ) -> None:
        # self.placed_list : 'list[list[str]]' = placed_list
        self.placed_list: "list[PlacedClause]" = placed_list
        self.program: Program = program
        # self.background : 'list[str]' = background
        # self.positive_examples : 'list[list[str]]' = positive_examples
        # self.negative_examples : 'list[list[str]]' = negative_examples
        self.args: Arguments = args
        # maximum number of AS to generate: this helps when the program has a generator
        # and there are too many options
        self.max_as_to_generate_foreach_program: int = 10000
        self.evaluate_score = evaluate_score
        self.population_initializer = population_initializer
        self.selection = selection
        self.pick_two = pick_two
        self.crossover = crossover
        self.mutation = mutation
        self.replacement = replacement

    @profile_phase("genetic")
    def genetic_solver(
        self,
        do_tournament: bool = True,  # choose tournament to pick the elements
        tournament_size: int = 12,  # number of elements considered for the tournament
        prob_replacing_oldest: float = 0.5,  # the probability to replace the oldest instead of the one with the lowest fittness
        k_best_for_the_next_round: int = 5,  # the top k individuals to keep for the next round
    ) -> "tuple[list[str], float, bool, list[int]]":
        """
        Genetic algorithm to find the best program
        """

        ###### BODY OF THE METHOD ######

        # step 0: initialize the population
        population: "list[Individual]" = []
        best_found = False

        population, best_found = self.population_initializer(
            self.args.clauses_per_individual,
            self.placed_list,
            self.args.population_size,
            self.evaluate_score,
        )

        if best_found:
            record_ga_generation(0, [population[0].score], population[0].score)
            return population[0].program, population[0].score, True, [-1]

        # step 1: sort in terms of decreasing fitness
        population.sort(key=lambda x: x.score, reverse=True)

        # step 2: iterate trough programs
        print(f"Running for {self.args.iterations_genetic} iterations")
        start_time = time.time()
        best_score_so_far = population[0].score
        for it in range(self.args.iterations_genetic + 1):
            best_score_so_far = max(best_score_so_far, population[0].score)
            record_ga_generation(it, [el.score for el in population], best_score_so_far)
            # print(f"it: {it}")
            if it % 100 == 0:
                print(
                    f"Iteration {it} - taken for 100: {time.time() - start_time} - best: {population[0]}"
                )
                start_time = time.time()
            # 2.1: selection of the two fittest elements
            # print('pre tournament')
            if do_tournament:
                best_a = self.selection(population, tournament_size)
                best_b = self.selection(population, tournament_size)
            else:
                best_a, best_b = self.pick_two(population)

            # either do crossover or mutation seems to be not effective
            # prob_crossover = 0.05

            # 2.2: crossover
            # print('pre cross')
            new_program_1, new_program_2 = self.crossover(
                best_a, best_b, self.evaluate_score
            )
            # If the best found, stop the iteration
            # _, is_best, l_best_indexes = evaluate_score([], [], new_program_1.program)
            for prg in [new_program_1, new_program_2]:
                if prg.is_best:
                    return (
                        [prg.program[i] for i in prg.l_best_indexes],
                        prg.score,
                        True,
                        [-1],
                    )

            # 2.3: mutation
            # https://arxiv.org/pdf/2305.01582.pdf
            # print('pre mutate')
            new_mutated_1 = self.mutation(
                new_program_1,
                self.placed_list,
                self.args.mutation_probability,
                self.evaluate_score,
            )
            new_mutated_2 = self.mutation(
                new_program_2,
                self.placed_list,
                self.args.mutation_probability,
                self.evaluate_score,
            )

            l_mutated = [new_mutated_1, new_mutated_2]

            # 3: replace elements in the population
            # print('pre replace')
            for el in l_mutated:
                # if best, return
                if el.is_best:
                    return (
                        [el.program[i] for i in el.l_best_indexes],
                        el.score,
                        True,
                        [-1],
                    )

                population = self.replacement(population, el, prob_replacing_oldest)

        print("Iterations completed")

        # keep the elements for the next round: extract all the stubs from
        # the top k programs. Then, count the occurrences of each and return the top
        # k stubs that occur the most
        all_indexes_list: "list[int]" = []
        for i in range(1, k_best_for_the_next_round + 1):
            print(population[i].program)
            all_indexes_list.extend(population[i].stub_indexes)

        # create a dict to count the occurrences, sort it, and return the top
        # k elements that occur the most
        s = {x: all_indexes_list.count(x) for x in set(all_indexes_list)}
        a = sorted(s.items(), key=lambda x: x[1], reverse=True)

        with phase("fitness.final"):
            res = self.evaluate_score(
                population[0].stub_indexes,
                population[0].prog_indexes,
                population[0].program,
            )

        return (
            [population[0].program[i] for i in population[0].l_best_indexes],
            res[0],
            False,
            [i[0] for i in a[:k_best_for_the_next_round]],
        )
