import itertools

from gtnhvelo.gtnh.overclocks import OverclockHandler
from ._utils import userRound

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gtnhvelo.cli import ProgramContext
    from gtnhvelo.data.basicTypes import Recipe


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
            recipes[i] = oh.overclockRecipe(rec)
            rec.base_eut = rec.eut

        # DEBUG
        for rec in recipes:
            self.parent_context.cLog(rec)
        self.parent_context.cLog('')

    @staticmethod
    def userRound(number: int | float) -> str:
        return userRound(number)

    # Graph utility functions
    from ._utils import (  # type: ignore
        addNode,
        addEdge,
        tierToVoltage,
        createAdjacencyList,
        _iterateOverMachines,
        _checkIfMachine,
    )

    # Setup of graph - connect edges and remove cycles
    from ._preProcessing import (  # type: ignore
        connectGraph,
        removeBackEdges,
    )

    # Main runtime - describes primary behavior
    from ._core import (  # type: ignore
        balanceGraph,
        outputGraphviz
    )

    # Machine locking - core autobalancing functionality
    from ._machineLocking import (  # type: ignore
        _lockMachine,
        _lockMachineEdges,
        _simpleLockMachineEdges,
    )

    # Utilities for "port node" style graphviz nodes
    from ._portNodes import (  # type: ignore
        stripBrackets,
        nodeHasPort,
        getOutputPortSide,
        getInputPortSide,
        getUniqueColor,
        getPortId,
        getIngId,
        getIngLabel,
        getQuantLabel,
        _combineInputs,
        _combineOutputs,
    )

    # Add summary and power burning machines
    from ._postProcessing import (  # type: ignore
        _addSummaryNode,
        _addPowerLineNodes,
        bottleneckPrint,
    )
