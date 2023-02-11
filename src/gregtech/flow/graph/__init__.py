"""The main graph logic of GT: Flow."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from gregtech.flow.gtnh.overclocks import OverclockHandler

from ._utils import round_readable

if TYPE_CHECKING:
    from gregtech.flow.cli import ProgramContext
    from gregtech.flow.recipe.basic_types import Recipe


class Graph:
    """Graphviz Graph abstraction for GT: Flow."""

    def __init__(self, graph_name: str, recipes: list,
                 parent_context: ProgramContext, title: str = ''):
        """Initializes Graph and also overclocks all recipes.

        Args:
            graph_name (str): Graph name, used as a title
            recipes (list): List of recipes
            parent_context (ProgramContext): ProgramContext object
            title (str, optional): The title of the graph. Defaults to '.
        """
        self.graph_name = graph_name
        self.recipes: dict[str, Recipe] = {str(i): x for i, x in enumerate(recipes)}
        self.nodes: dict = {}
        self.edges: dict = {}  # uniquely defined by (machine from, machine to, ing name)
        self.parent_context = parent_context
        self.graph_config = parent_context.graph_config
        self.title = title

        # Populated later on
        self.adj: dict = {}
        self.adj_machine: dict = {}

        self._color_dict: dict = {}
        if self.graph_config.get('USE_RAINBOW_EDGES', None):
            self._color_cycler = itertools.cycle(self.graph_config['EDGECOLOR_CYCLE'])
        else:
            self._color_cycler = itertools.cycle(['#ffffff'])

        # Overclock all recipes to the provided user voltage
        oh = OverclockHandler(self.parent_context)
        for i, rec in enumerate(recipes):
            recipes[i] = oh.overclock_recipe(rec)
            rec.base_eut = rec.eut

        # DEBUG
        for rec in recipes:
            self.parent_context.log(rec)
        self.parent_context.log('')
        self._machine_check.cache_clear()

    @staticmethod
    def round_readable(number: int | float) -> str:
        """Transforms a number into a more readable form by using orders of magnitude.

        For example: 10K, 27.5B, 55T, etc.

        Args:
            number (int | float): Input number.

        Raises:
            NotImplementedError: Negative number not allowed.

        Returns:
            str: Readable number in string form
        """
        return round_readable(number)

    def add_node(self: Graph, recipe_id: str, **kwargs) -> None:
        """Adds a node to the Graph.

        Args:
            recipe_id (str): Recipe ID in string form
            **kwargs: Kwargs of the recipe ID
        """
        self.nodes[recipe_id] = kwargs

    def add_edge(self: Graph, node_from: str, node_to: str,
                 ing_name: str, quantity: float | int, **kwargs) -> None:
        """Adds an edge to the Graph.

        Args:
            node_from (str): Origin node
            node_to (str): Destination node
            ing_name (str): Ingredient name
            quantity (float | int): Ingredient quantity
        """
        self.edges[(node_from, node_to, ing_name)] = {
            'quant': quantity,
            'kwargs': kwargs
        }

    # Imports
    from ._port_nodes import _combine_inputs  # type: ignore
    from ._port_nodes import _combine_outputs  # type: ignore
    from ._port_nodes import (check_node_has_port, get_ing_id,  # type: ignore
                              get_ing_label, get_input_port_side,
                              get_output_port_side, get_port_id,
                              get_quant_label, get_unique_color,
                              strip_brackets)
    from ._utils import (_machine_check, _machine_iterate,  # type: ignore
                         create_adjacency_list, idx_to_voltage)
