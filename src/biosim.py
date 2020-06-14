# -*- coding: utf-8 -*-

from src.animal import Herbivore, Carnivore, Animal
from src.landscape import Island
from src.plotting import Plotting

import random as random
import numpy as np
import time


class BioSim:
    """Main BioSim class for running simulations"""

    def __init__(
        self,
        island_map=None,
        ini_pop=[],
        seed=123,
        ymax_animals=None,
        cmax_animals=None,
        hist_specs=None,
        img_base=None,
        img_fmt="png",
        plot_graph=False,
    ):
        """
        :param island_map: Multi-line string specifying island geography
        :param ini_pop: List of dictionaries specifying initial population
        :param seed: Integer used as random number seed
        :param ymax_animals: Number specifying y-axis limit for graph showing animal numbers
        :param cmax_animals: Dict specifying color-code limits for animal densities
        :param hist_specs: Specifications for histograms, see below
        :param img_base: String with beginning of file name for figures, including path
        :param img_fmt: String with file type for figures, e.g. 'png'
        If ymax_animals is None, the y-axis limit should be adjusted automatically.
        If cmax_animals is None, sensible, fixed default values should be used.
        cmax_animals is a dict mapping species names to numbers, e.g.,
        {'Herbivore': 50, 'Carnivore': 20}
        hist_specs is a dictionary with one entry per property for which a histogram shall be shown.
        For each property, a dictionary providing the maximum value and the bin width must be
        given, e.g.,
        {'weight': {'max': 80, 'delta': 2}, 'fitness': {'max': 1.0, 'delta': 0.05}}
        Permitted properties are 'weight', 'age', 'fitness'.
        If img_base is None, no figures are written to file.
        Filenames are formed as
        '{}_{:05d}.{}'.format(img_base, img_no, img_fmt)
        where img_no are consecutive image numbers starting from 0.
        img_base should contain a path and beginning of a file name.
        """

        if island_map is None:
            map_str = """WWW\nWLW\nWWW"""
            self._island = Island(map_str)
        elif type(island_map) == str:
            self._island = Island(island_map)
        else:
            raise ValueError("Map string needs to be of type str!")

        self._ymax = ymax_animals
        self._cmax = cmax_animals

        if hist_specs is not None:
            pass

        self.add_population(ini_pop)

        self._year = 0
        self._plot_bool = plot_graph
        self._plot = None
        self._img_base = img_base
        self._img_fmt = img_fmt

        random.seed(seed)

    @staticmethod
    def set_animal_parameters(species, params):
        """
        Set parameters for animal species.
        :param species: String, name of animal species
        :param params: Dict with valid parameter specification for species
        """
        if species == 'Herbivore':
            print(species)
            Herbivore.set_params(params)
        elif species == 'Carnivore':
            print(species)
            Carnivore.set_params(params)
        else:
            raise ValueError('species needs to be either Herbivore or Carnivore!')

    def set_landscape_parameters(self, landscape, params):
        """
        Set parameters for landscape type.
        :param landscape: String, code letter for landscape
        :param params: Dict with valid parameter specification for landscape
        """
        self._island.set_landscape_params(landscape, params)

    def add_population(self, population):
        """
        Add a population to the island
        :param population: List of dictionaries specifying population
        """
        if type(population) == list:
            for loc_dict in population:  # This loop will be replaced with a more elegant iteration
                new_animals = [
                        Herbivore.from_dict(animal_dict)
                        if animal_dict["species"] == "Herbivore"
                        else Carnivore.from_dict(animal_dict)
                        for animal_dict in loc_dict["pop"]
                    ]
                self._island.landscape[loc_dict["loc"]].add_animals(new_animals)
                self._island.count_animals(animal_list=new_animals)
        else:
            raise ValueError(f'Pop list needs to be a list of dicts! Was of type {type(population)}.')

    def feeding(self, cell):
        """Iterates through each animal in the cell and feeds it according to species

        :param cell: Current cell object
        :type cell: object
        """
        cell.fodder = cell.f_max()
        # Randomize animals before feeding
        cell.randomize_herbs()

        for herb in cell.herbivores:  # Herbivores eat first
            if cell.fodder > 0:
                herb.eat_fodder(cell)

        for carn in cell.carnivores:  # Carnivores eat last
            herbs_killed = carn.kill_prey(cell.sorted_herbivores)  # Carnivore hunts for herbivores
            cell.remove_animals(herbs_killed)  # Remove killed animals from cell
            self._island.del_animals(num_herbs=len(herbs_killed))

    def procreation(self, cell):
        """Iterates through each animal in the cell and procreates

        :param cell: Current cell object
        :type cell: object
        """
        new_herbs = []
        new_carns = []
        n_herbs, n_carns = cell.herb_count, cell.carn_count

        for herb in cell.herbivores:  # Herbivores give birth)
            give_birth, birth_weight = herb.give_birth(n_herbs)

            if give_birth:
                new_herbs.append(Herbivore(weight=birth_weight, age=0))

        for carn in cell.carnivores:  # Carnivores give birth
            give_birth, birth_weight = carn.give_birth(n_carns)

            if give_birth:
                new_carns.append(Carnivore(weight=birth_weight, age=0))

        cell.add_animals(new_herbs + new_carns)  # Add new animals to cell

        self._island.count_animals(num_herbs=len(new_herbs), num_carns=len(new_carns))

    def migrate(self, cell):
        """Iterates through each animal in the cell and migrates

        :param loc: Coordinate of current cell
        :type loc: tuple
        :param cell: Current cell object
        :type cell: object
        :param all_migrated_animals: Updated list of animals that have migrated the current year
        :type all_migrated_animals: list
        """
        # Define neighbor cells once:

        migrated_animals = []
        for animal in cell.animals:
            if not animal.has_moved and animal.migrate():
                if len(cell.land_cell_neighbors) > 0:
                    chosen_cell = random.choice(cell.land_cell_neighbors)
                    chosen_cell.add_animals([animal])
                    migrated_animals.append(animal)

                animal.has_moved = True

        cell.remove_animals(migrated_animals)
        cell.reset_animals()

    def run_year_cycle(self):
        """
        Runs through each of the 6 yearly seasons for all cells
        """
        for loc, cell in self._island.land_cells.items():
            #  1. Feeding
            self.feeding(cell)

            #  2. Procreation
            self.procreation(cell)

            # 3. Migration
            self.migrate(cell)

            #  4. Aging
            for animal in cell.animals:
                animal.aging()

            #  5. Loss of weight
            for animal in cell.animals:
                animal.lose_weight()

            #  6. Death
            dead_animals = []

            for animal in cell.animals:
                if animal.death():
                    dead_animals.append(animal)

            cell.remove_animals(dead_animals)
            self._island.del_animals(animal_list=dead_animals)

        self._year += 1  # Add year to simulation

    def simulate(self, num_years, vis_years=1, img_years=None):
        """
        Run simulation while visualizing the result.
        :param num_years: number of years to simulate
        :param vis_years: years between visualization updates
        :param img_years: years between visualizations saved to files (default: vis_years)
        Image files will be numbered consecutively.
        """
        start_time = time.time()

        if self._plot_bool and self._plot is None:
            self._plot = Plotting(self._island,
                                  cmax=self._cmax,
                                  ymax=self._ymax)
            self._island.update_pop_matrix()
            self._plot.init_plot(num_years)
            self._plot.y_herb[self._year] = self._island.num_herbs
            self._plot.y_carn[self._year] = self._island.num_carns

        elif self._plot_bool:
            self._plot.y_herb += [np.nan for _ in range(num_years)]
            self._plot.y_carn += [np.nan for _ in range(num_years)]

        for _ in range(num_years):
            self.run_year_cycle()
            print(f"Year: {self._year}")
            print(f"Animals: {self._island.num_animals}")
            print(f"Herbivores: {self._island.num_herbs}")
            print(f"Carnivore: {self._island.num_carns}")
            if self._plot_bool:
                self._plot.y_herb[self._year] = self._island.num_herbs
                self._plot.y_carn[self._year] = self._island.num_carns
                if self._year % vis_years == 0:
                    self._island.update_pop_matrix()
                    self._plot.update_plot()

            if self._img_base is not None:
                if img_years is None:
                    if self._year % vis_years == 0:
                        self._plot.save_graphics(self._img_base, self._img_fmt)

                else:
                    if self._year % img_years == 0:
                        self._plot.save_graphics(self._img_base, self._img_fmt)

        finish_time = time.time()

        print("Simulation complete.")
        print("Elapsed time: {:.3} seconds".format(finish_time - start_time))
        # input('Press enter to continue')

    @property
    def year(self):
        """Last year simulated."""
        return self._year

    @property
    def num_animals(self):
        """Total number of animals on island."""
        return self._island.num_animals

    @property
    def num_animals_per_species(self):
        """Number of animals per species in island, as dictionary."""
        return {"Herbivore": self._island.num_herbs, "Carnivore": self._island.num_carns}

    # def make_movie(self):
    #     """Create MPEG4 movie from visualization images saved."""
    #     pass
