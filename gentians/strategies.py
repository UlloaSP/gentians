import random
import re
import sys
import math
import time
from contextlib import nullcontext

from .clingo_interface import ClingoInterface
from .arguments import Arguments
from .parser import Program
from .utils import get_atoms


class PlacedClause:
    '''
    Class containing a clause.
    '''
    def __init__(self,
        placed_clauses : 'list[str]'
        ) -> None:
        self.placed_clauses = placed_clauses
        self.n_vars_clauses : 'list[int]' = []
        self.n_atoms = 0

        regex = r"V\d+"
        r = re.compile(regex)

        for cl in self.placed_clauses:
            v = len(set(r.findall(cl)))
            self.n_vars_clauses.append(v)

        self.n_atoms += len(get_atoms(placed_clauses[0]))


    def __str__(self) -> str:
        s = ""
        for cl in self.placed_clauses:
            s += cl + '\n'
        s += f"n_vars: {self.n_vars_clauses}\nn_atoms: {self.n_atoms}\n"
        return s

    def __repr__(self) -> str:
        return self.__str__()


class Strategy:
    def __init__(self,
            placed_list : 'list[PlacedClause]',
            # background : 'list[str]',
            # positive_examples : 'list[list[str]]',
            # negative_examples : 'list[list[str]]',
            program : Program,
            args : Arguments,
        ) -> None:
        # self.placed_list : 'list[list[str]]' = placed_list
        self.placed_list : 'list[PlacedClause]' = placed_list
        self.program : Program = program
        # self.background : 'list[str]' = background
        # self.positive_examples : 'list[list[str]]' = positive_examples
        # self.negative_examples : 'list[list[str]]' = negative_examples
        self.args : Arguments = args
        self.profiler = getattr(args, "profiler", None)
        # maximum number of AS to generate: this helps when the program has a generator
        # and there are too many options
        self.max_as_to_generate_foreach_program : int = 10000

    def _span(self, name: str, **metadata):
        if self.profiler is None:
            return nullcontext()
        return self.profiler.span(name, **metadata)

    def genetic_solver(self,
            do_tournament : bool = True, # choose tournament to pick the elements
            tournament_size : int = 12, # number of elements considered for the tournament
            prob_replacing_oldest : float = 0.5, # the probability to replace the oldest instead of the one with the lowest fittness
            k_best_for_the_next_round : int = 5 # the top k individuals to keep for the next round
        ) -> 'tuple[list[str], float, bool, list[int]]':
        '''
        Genetic algorithm to find the best program
        '''
        class Individual:
            def __init__(self,
                    program : 'list[str]',
                    stub_indexes : 'list[int]',
                    prog_indexes : 'list[int]',
                    score : float,
                    is_best : bool = False, # does this cover everything positive and no negative?
                    l_best_indexes : 'list[int]' = [] # best indexes, if it is the best
                ) -> None:
                self.program = program
                # stub_indexes is a list of int representing the index of the stub 
                # clauses selected
                self.stub_indexes = stub_indexes
                # prog_indexes is a list of int representing the index of the program 
                # selected for the stub_indexes clauses - maybe not needed
                self.prog_indexes = prog_indexes
                self.score = score
                self.is_best = is_best
                self.l_best_indexes = l_best_indexes
                self.generated_timestamp = time.time()

            def __str__(self) -> str:
                return f"Program: {self.program} - score: {self.score}"

            def __repr__(self) -> str:
                return self.__str__()


        def evaluate_score(
                stub_indexes : 'list[int]',
                prog_indexes : 'list[int]',
                program : 'list[str]'
            ) -> 'tuple[float, bool, list[int]]':
            '''
            Evaluates the score of an individual: first it computes the covered positive
            and negative for every subset of the clauses. Then, the score of every
            subset is defined as math.exp(covered_pos/tot_pos - covered_neg/tot_neg)*10.
            Simply considering the difference I think it is not enough (specially when
            there are few positive examples).
            The score of an individual is the average of the scores.
            '''
            with self._span("genetic.evaluation.total", clauses=len(program)):
                asp_solver = ClingoInterface(
                    self.program.background,
                    [f'{self.max_as_to_generate_foreach_program}', '--project'],
                    profiler=self.profiler,
                    phase="genetic.evaluation"
                )

                cov = asp_solver.extract_coverage_and_set_clauses(
                    program, self.program.positive_examples, self.program.negative_examples, False
                )

            # print(cov)
            
            best_found = False
            l_index : 'list[int]' = []
            l_best_indexes : 'list[str]' = []
            scores : 'list[float]' = []

            for res, element_coverage in cov.items():
                if res != "Error" and res != "Undefined":
                    # set to remove duplicates
                    cp : int = len(list(set(element_coverage.l_pos)))
                    cn : int = len(list(set(element_coverage.l_neg)))

                    # scores.append(math.exp((cp - cn)))
                    v_pos = (cp/len(self.program.positive_examples)) if len(self.program.positive_examples) > 0 else 0
                    v_neg = (cn/len(self.program.negative_examples)) if len(self.program.negative_examples) > 0 else 0
                    scores.append(math.exp((v_pos - v_neg)*10))
                    # consideration: here, [0,1] and [1,2] have the same score
                    # where the first element is the covered positive and the
                    # second is covered negative. However, is the first worst
                    # than the second (the first only covers 1 negative example)
                    # while the second two but it has one positive covered

                    # print(self.positive_examples,self.negative_examples)
                    # print(cp,cn)
                    if cp == len(self.program.positive_examples):
                        if cn == 0:
                            print(f"Best found with indexes {res}")
                            print(program)
                            l_best_indexes.append(res)
                            best_found = True
                        # else:
                        #     print("Coverage 100% of the positive with")
                        # print([program[i] for i in l_index], cp, cn)

            # mean
            if len(scores) > 0:
                score = sum(scores)/len(scores)
            else:
                score = -2000
            
            # if the best has not been found, still compute the current best
            # which is the one with the lowest associated cost. If two programs
            # have the same cost, pick the one with the lowest number of clauses.
            if not best_found:
                current_min_el : str = next(iter(cov.keys()))
                for k, v in cov.items():
                    if v.get_cost() < cov[current_min_el].get_cost() or (v.get_cost() == cov[current_min_el].get_cost() and len(k) < len(current_min_el)):
                        current_min_el = k
                if current_min_el != "Undefined":
                    l_best_indexes = [current_min_el]

            # shortest one
            l_best_indexes.sort(key = lambda s : len(s))
            l_index = [int(v) for v in list(l_best_indexes[0])] if len(l_best_indexes) > 0 else []

            return score, best_found, l_index
    
        def get_fittest(selected_individuals : 'list[Individual]') -> Individual:
            '''
            Returns the fittest element in the current selection
            '''
            return max(selected_individuals, key=lambda x : x.score)

        
        def tournament(
            population: 'list[Individual]',
            tournament_size : int = 12,
            prob_selecting_fittest : float = 0.9
            ):
            '''
            Tournament to select the individuals to combine and mutate
            '''
            tournament_size = min(tournament_size, len(population))
            random_subset = random.sample([x for x in population], tournament_size)
            stop = False
            best_element = get_fittest(random_subset)
            while len(random_subset) > 1 and not stop:
                if random.random() > prob_selecting_fittest:
                    random_subset.remove(best_element)
                    best_element = get_fittest(random_subset)
                else:
                    stop = True

            return best_element
        
        
        def pick_two_fittest(
            population: 'list[Individual]',
            pick_uniform : bool = True
            ) -> 'tuple[Individual,Individual]':
            '''
            Pick the two fittest elements.
            If pick_uniform is true, select a random element between the ones with
            the highest fit (since most programs have the same fitness).
            '''
            max_score = population[0].score
            i = 1
            j = 1
            for i in range(1, len(population)):
                if population[i].score < max_score:
                    break

            if i < 2:
                max_score = population[i].score
                for j in range(i, len(population)):
                    if population[j].score < max_score:
                        break
            else:
                j = i

            # 2.1: pick the two fittest
            if not pick_uniform:
                # this is the naive version. However, since many programs have the same
                # score, # i should choose a random one among these
                best_a = population[0]
                best_b = population[1]
            else:
                idx_a, idx_b = random.sample(range(0, j), 2)
                # print(f"Combining: {idx_a}, {idx_b}")
                best_a = population[idx_a]
                best_b = population[idx_b]

            return best_a, best_b

        
        def crossover(best_a : Individual, best_b : Individual) -> 'tuple[Individual,Individual]':
            '''
            Crossover: pick a random index and generate a element
            '''
            crossover_position = random.randint(0, len(best_a.program) - 1)
            # print(f"Crossover: {crossover_position}")
            new_program = list(best_a.program[:crossover_position] + best_b.program[crossover_position:])
            new_stub_indexes = best_a.stub_indexes[:crossover_position] + best_b.stub_indexes[crossover_position:]
            new_program_indexes = best_a.prog_indexes[:crossover_position] + best_b.prog_indexes[crossover_position:]
            current_score, is_best, l_indexes = evaluate_score(new_stub_indexes, new_program_indexes, new_program)
            i0 = Individual(new_program, new_stub_indexes, new_program_indexes, current_score, is_best, l_indexes)

            new_program = list(best_b.program[:crossover_position] + best_a.program[crossover_position:])
            new_stub_indexes = best_b.stub_indexes[:crossover_position] + best_a.stub_indexes[crossover_position:]
            new_program_indexes = best_b.prog_indexes[:crossover_position] + best_a.prog_indexes[crossover_position:]
            current_score, is_best, l_indexes = evaluate_score(new_stub_indexes, new_program_indexes, new_program)
            i1 = Individual(new_program, new_stub_indexes, new_program_indexes, current_score, is_best, l_indexes)

            return i0, i1
        
        
        def mutate(element : Individual, change_stub : bool = True):
            '''
            Mutation of an element
            '''
            change_stub = True
            new_element = element
            something_changed = False
            
            for i, _ in enumerate(element.program):
                if random.random() < self.args.mutation_probability:
                    something_changed = True
                    # versione 1: cambio solamente il posizionamento delle variabili
                    if not change_stub:
                        possibilities = self.placed_list[element.stub_indexes[i]]
                        rand_el = random.randint(0, len(possibilities.placed_clauses) - 1)
                        new_element.program[i] = possibilities.placed_clauses[rand_el]
                        new_element.prog_indexes[i] = rand_el
                    else:
                        # versione 2: cambio la regola
                        new_stub = random.randint(0, len(self.placed_list) - 1)
                        new_prog_pos = random.randint(0, len(self.placed_list[new_stub].placed_clauses) - 1)
                        # print(f"{new_program[i]} replaced with")
                        new_element.program[i] = self.placed_list[new_stub].placed_clauses[new_prog_pos]
                        # print(f"This: {new_program[i]}")
                        new_element.prog_indexes[i] = new_prog_pos
                        new_element.stub_indexes[i] = new_stub
            
            # TODO: add annealing to accept or reject the mutated program?
            # compute the new score if something has changed
            if something_changed:
                new_element.generated_timestamp = time.time()
                new_element.score, new_element.is_best, new_element.l_best_indexes = evaluate_score(
                    new_element.stub_indexes, new_element.prog_indexes, new_element.program
                )
            
            return new_element


        def initialize_population(
            number_clauses : int,
            # placed_list : 'list[list[str]]',
            placed_list : 'list[PlacedClause]',
            population_size : int
            ) -> 'tuple[list[Individual],bool]':
            '''
            Initialize the population of individuals
            '''
            sampled_individuals : 'list[Individual]' = []
            best_found = False
            
            while len(sampled_individuals) < population_size:
                # pick a program
                # TODO: non necessariamente il sampling deve essere senza ripetizioni
                stub_indexes : 'list[int]' = sorted(
                    random.sample(
                        range(len(self.placed_list)),
                        number_clauses if len(placed_list) > number_clauses
                                        else len(placed_list)
                    )
                )

                # for every index, select one of the possible variable placement
                program : 'list[str]' = []
                prog_indexes : 'list[int]' = []
                for i in stub_indexes:
                    # el = random.randint(0, len(placed_list[i]) - 1)
                    el = random.randint(0, len(placed_list[i].placed_clauses) - 1)
                    prog_indexes.append(el)
                    # program.append(placed_list[i][el])
                    program.append(placed_list[i].placed_clauses[el])

                program = sorted(program)
                # cp is the current program
                # cp, cn, current_score, best_found, l_index = evaluate_score(program)
                # print("evaluate score in init")
                current_score, best_found, l_index = evaluate_score(stub_indexes, prog_indexes, program)

                if best_found:
                    # TODO: restituire anche la combinazione di elementi
                    return [Individual([program[i] for i in l_index], stub_indexes, prog_indexes, current_score)], best_found

                sampled_individuals.append(Individual(program, stub_indexes, prog_indexes, current_score))

            return sampled_individuals, best_found

        ###### BODY OF THE METHOD ######

        # step 0: initialize the population
        population : 'list[Individual]' = []
        best_found = False

        with self._span("genetic.initialize_population", population_size=self.args.population_size):
            population, best_found = initialize_population(
                self.args.clauses_per_individual,
                self.placed_list,
                self.args.population_size
            )

        if best_found:
            return population[0].program, population[0].score, True, [-1]

        # step 1: sort in terms of decreasing fitness
        population.sort(key = lambda x : x.score, reverse=True)

        # step 2: iterate trough programs
        print(f"Running for {self.args.iterations_genetic} iterations")
        start_time = time.time()
        for it in range(self.args.iterations_genetic + 1):
            if self.profiler is not None and len(population) > 0:
                self.profiler.record_fitness(
                    it,
                    population[0].score,
                    sum(ind.score for ind in population) / len(population)
                )
            # print(f"it: {it}")
            if it % 100 == 0:
                print(f"Iteration {it} - taken for 100: {time.time() - start_time} - best: {population[0]}")
                start_time = time.time()
            # 2.1: selection of the two fittest elements
            # print('pre tournament')
            with self._span("genetic.selection"):
                if do_tournament:
                    best_a = tournament(population, tournament_size)
                    best_b = tournament(population, tournament_size)
                else:
                    best_a, best_b = pick_two_fittest(population)
            

            # either do crossover or mutation seems to be not effective
            # prob_crossover = 0.05
            
            # 2.2: crossover
            # print('pre cross')
            with self._span("genetic.crossover"):
                new_program_1, new_program_2 = crossover(best_a, best_b)
            # If the best found, stop the iteration
            # _, is_best, l_best_indexes = evaluate_score([], [], new_program_1.program)
            for prg in [new_program_1, new_program_2]:
                if prg.is_best:
                    return [prg.program[i] for i in prg.l_best_indexes], prg.score, True, [-1]
            
            # 2.3: mutation
            # https://arxiv.org/pdf/2305.01582.pdf
            # print('pre mutate')
            with self._span("genetic.mutation"):
                new_mutated_1 = mutate(new_program_1)
                new_mutated_2 = mutate(new_program_2)
            
            l_mutated = [new_mutated_1, new_mutated_2]
            
            # 3: replace elements in the population
            # print('pre replace')
            with self._span("genetic.replacement"):
                for el in l_mutated:
                    # if best, return
                    if el.is_best:
                        return [el.program[i] for i in el.l_best_indexes], el.score, True, [-1]

                    found = False
                    # if not best, check whether it is already in the population
                    for pop in population:
                        if sorted(pop.program) == sorted(el.program):
                            found = True
                            break
                    
                    # if not in the population, insert
                    if not found:
                        i = 0
                        for i, element in enumerate(population):
                            # equal to have some variability?
                            if el.score >= element.score:
                                break
                        population.insert(i, el)

                        # drop the element
                        if random.random() < prob_replacing_oldest:
                            # drop the oldest element
                            oldest = min(population, key=lambda x : x.generated_timestamp)
                            population.remove(oldest)
                        else:
                            # drop the element with the lowest fitness
                            population = population[:-1]

        print("Iterations completed")
        
        # keep the elements for the next round: extract all the stubs from
        # the top k programs. Then, count the occurrences of each and return the top
        # k stubs that occur the most
        all_indexes_list : 'list[int]' = [] 
        for i in range(1, min(k_best_for_the_next_round + 1, len(population))):
            print(population[i].program)
            all_indexes_list.extend(population[i].stub_indexes)
        
        # create a dict to count the occurrences, sort it, and return the top
        # k elements that occur the most
        s = {x:all_indexes_list.count(x) for x in set(all_indexes_list)}
        a = sorted(s.items(), key=lambda x: x[1], reverse=True)

        res = evaluate_score(population[0].stub_indexes,population[0].prog_indexes, population[0].program)

        return [population[0].program[i] for i in population[0].l_best_indexes], res[0], False, [i[0] for i in a[:k_best_for_the_next_round]]
