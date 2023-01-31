from collections import defaultdict
from functools import lru_cache

from gregtech.flow.data.basic_types import Recipe


def swap_io(io_type):
    if io_type == 'I':
        return 'O'
    elif io_type == 'O':
        return 'I'
    else:
        raise RuntimeError(f'Improper I/O type: {io_type}')


def add_node(self, recipe_id, **kwargs):
    self.nodes[recipe_id] = kwargs


def add_edge(self, node_from, node_to, ing_name, quantity, **kwargs):
    self.edges[(node_from, node_to, ing_name)] = {
        'quant': quantity,
        'kwargs': kwargs
    }


def round_readable(number: int | float) -> str:
    # Display numbers nicely for end user (eg. 814.3k)
    # input int/float, return string
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
    raise NotImplementedError('Negative number not allowed')


def create_adjacency_list(self):
    # Compute "adjacency list" (node -> {I: edges, O: edges}) for edges and machine-involved edges
    adj = defaultdict(lambda: defaultdict(list))
    adj_machine = defaultdict(lambda: defaultdict(list))
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


def tier_to_voltage(self, tier_idx):
    # Return voltage from tier index
    return 32 * pow(4, tier_idx)


@lru_cache(maxsize=256)  # Arbitrary amount
def _machine_check(self, rec_id):
    if rec_id in {'source', 'sink', 'total_io_node'} or rec_id.startswith(('power_', 'joint_')):
        return False
    return True


def _machine_iterate(self):
    # Iterate over non-source/sink noedes and non power nodes
    for rec_id in self.nodes:
        if self._machine_check(rec_id):
            yield self.recipes[rec_id]
