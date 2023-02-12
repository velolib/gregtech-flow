from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from typing import TYPE_CHECKING

from gregtech.flow.recipe.basic_types import Recipe

if TYPE_CHECKING:
    from collections.abc import Iterator

    from gregtech.flow.graph import Graph


def swap_io(io_type: str) -> str:
    """Swaps I to O and vice versa.

    Args:
        io_type (str): I or O as strings

    Raises:
        RuntimeError: Improper I/O string

    Returns:
        str: O or I depending on io_type
    """
    if io_type == 'I':
        return 'O'
    elif io_type == 'O':
        return 'I'
    else:
        raise ValueError(f'Improper I/O string: {io_type}')


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
    cutoffs: dict = {
        1_000_000_000_000: lambda x: f'{round(x/1_000_000_000_000, 2)}T',
        1_000_000_000: lambda x: f'{round(x/1_000_000_000, 2)}B',
        1_000_000: lambda x: f'{round(x/1_000_000, 2)}M',
        1_000: lambda x: f'{round(x/1_000, 2)}K',
        0: lambda x: f'{round(x, 2)}'
    }

    for n, roundfxn in cutoffs.items():
        if abs(number) >= n:
            rounded: str = roundfxn(number)
            return rounded
    raise ValueError('Negative number not allowed!')


def create_adjacency_list(self: Graph) -> None:
    """Computes an adjacency list (node -> {I: edges, O: edges})."""
    # Compute "adjacency list" (node -> {I: edges, O: edges}) for edges and machine-involved edges
    adj: dict = defaultdict(lambda: defaultdict(list))
    adj_machine: dict = defaultdict(lambda: defaultdict(list))
    for edge in self.edges:
        node_from, node_to, ing_name = edge
        adj[node_from]['O'].append(edge)
        adj[node_to]['I'].append(edge)
        if node_to not in {'sink', 'source'}:
            adj_machine[node_from]['O'].append(edge)
        if node_from not in {'sink', 'source'}:
            adj_machine[node_to]['I'].append(edge)

    self.adj = adj
    self.adj_machine = adj_machine

    self.parent_context.log('Recomputing adjacency list...')
    for machine, io_group in self.adj_machine.items():
        machine_name = ''
        recipe_obj = self.recipes.get(machine)
        if isinstance(recipe_obj, Recipe):
            machine_name = recipe_obj.machine

        self.parent_context.log(f'{machine} {machine_name}')
        for io_type, edges in io_group.items():
            self.parent_context.log(f'{io_type} {edges}')
    self.parent_context.log('')


def idx_to_voltage(self: Graph, tier_idx: int) -> int:
    """Returns the amperage of the inputted tier.

    Args:
        tier_idx (int): Tier index.

    Returns:
        int: Tier index amperage.
    """
    return 32 * pow(4, tier_idx)


@lru_cache(maxsize=256)  # Arbitrary amount
def _machine_check(self: Graph, rec_id: str) -> bool:
    """Returns if inputted recipe ID is a machine and not a builtin.

    Args:
        rec_id (str): Recipe ID in string form.

    Returns:
        bool: Whether or not rec_id is a usable ID.
    """
    if rec_id in {'source', 'sink', 'total_io_node'} or rec_id.startswith(('power_', 'joint_')):
        return False
    return True


def _machine_iterate(self: Graph) -> Iterator[Recipe]:
    """Returns a generator of recipes.

    Yields:
        Generator[str, None, None]: Recipe generator.
    """
    # Iterate over non-source/sink noedes and non power nodes
    for rec_id in self.nodes:
        if self._machine_check(rec_id):
            yield self.recipes[rec_id]
