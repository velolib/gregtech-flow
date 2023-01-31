import itertools

from gregtech.flow.gtnh.overclocks import OverclockHandler
from ._utils import round_readable

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gregtech.flow.cli import ProgramContext
    from gregtech.flow.data.basicTypes import Recipe


class Graph:

    def __init__(self, graph_name: str, recipes: list, parent_context: 'ProgramContext', graph_config: dict = {}, title=None):
        self.graph_name = graph_name
        self.recipes: dict[str, 'Recipe'] = {str(i): x for i, x in enumerate(recipes)}
        self.nodes: dict = {}
        self.edges: dict = {}  # uniquely defined by (machine from, machine to, ing name)
        self.parent_context = parent_context
        self.graph_config = graph_config
        self.title = title

        # Populated later on
        self.adj: dict = {}
        self.adj_machine: dict = {}

        self._color_dict: dict = dict()
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
    def userRound(number: int | float) -> str:
        return round_readable(number)

    # Graph utility functions
    from ._utils import (  # type: ignore
        add_node,
        add_edge,
        tier_to_voltage,
        create_adjacency_list,
        _machine_iterate,
        _machine_check,
    )

    # Utilities for "port node" style graphviz nodes
    from ._portNodes import (  # type: ignore
        strip_brackets,
        check_node_has_port,
        get_output_port_side,
        get_input_port_side,
        get_unique_color,
        get_port_id,
        get_ing_id,
        get_ing_label,
        get_quant_label,
        _combine_inputs,
        _combine_outputs,
    )
