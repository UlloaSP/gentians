from ...arguments import Arguments
from ..individual import Individual
from ..types import (
    CrossoverFn,
    FitnessFn,
    MutationFn,
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
        placed_list: list[PlacedClause],
        program: Program,
        args: Arguments,
        evaluate_score: FitnessFn,
        population_initializer: PopulationInitializerFn,
        selection: SelectionFn,
        crossover: CrossoverFn,
        mutation: MutationFn,
        replacement: ReplacementFn,
    ) -> None:
        self.placed_list: list[PlacedClause] = placed_list
        self.program: Program = program
        self.args: Arguments = args
        self.evaluate_score = evaluate_score
        self.population_initializer = population_initializer
        self.selection = selection
        self.crossover = crossover
        self.mutation = mutation
        self.replacement = replacement

    @profile_phase("genetic")
    def genetic_solver(self) -> tuple[list[str], float, bool]:
        """
        Genetic algorithm to find the best program
        """

        # step 0: initialize the population
        population: list[Individual] = []
        best_found = False

        population, best_found = self.population_initializer(
            self.args.clauses_per_individual,
            self.placed_list,
            self.evaluate_score,
        )

        if best_found:
            record_ga_generation(0, [population[0].score], population[0].score)
            return population[0].program, population[0].score, True

        # step 1: sort in terms of decreasing fitness
        population.sort(key=lambda x: x.score, reverse=True)

        # step 2: iterate trough programs
        best_score_so_far = population[0].score
        for it in range(self.args.iterations_genetic + 1):
            best_score_so_far = max(best_score_so_far, population[0].score)
            record_ga_generation(it, [el.score for el in population], best_score_so_far)
            # 2.1: selection of the two fittest elements
            best_a, best_b = self.selection(population)

            # either do crossover or mutation seems to be not effective

            # 2.2: crossover
            known_signatures = {element.signature for element in population}
            new_program_1, new_program_2 = self.crossover(
                best_a, best_b, self.evaluate_score, known_signatures
            )
            # If the best found, stop the iteration
            # _, is_best, l_best_indexes = evaluate_score([], [], new_program_1.program)
            for prg in [new_program_1, new_program_2]:
                if prg.is_best:
                    return (
                        [prg.program[i] for i in prg.l_best_indexes],
                        prg.score,
                        True,
                    )

            # 2.3: mutation
            # https://arxiv.org/pdf/2305.01582.pdf
            new_mutated_1 = self.mutation(
                new_program_1,
                self.placed_list,
                self.evaluate_score,
                known_signatures,
            )
            new_mutated_2 = self.mutation(
                new_program_2,
                self.placed_list,
                self.evaluate_score,
                known_signatures,
            )

            l_mutated = [new_mutated_1, new_mutated_2]

            # 3: replace elements in the population
            for el in l_mutated:
                # if best, return
                if el.is_best:
                    return (
                        [el.program[i] for i in el.l_best_indexes],
                        el.score,
                        True,
                    )

                population = self.replacement(population, el)
            population.sort(key=lambda x: x.score, reverse=True)

        with phase("fitness.final"):
            res = self.evaluate_score(
                population[0].group_indexes,
                population[0].prog_indexes,
                population[0].program,
            )

        return (
            [population[0].program[i] for i in res[2]],
            res[0],
            False,
        )
