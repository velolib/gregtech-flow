from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gregtech.flow.graph import Graph

# This file is for the "port" style nodes
# as designed by Usagirei in https://github.com/OrderedSet86/gtnh-flow/pull/4


def strip_brackets(self: Graph, ing: str) -> str:
    """Strips brackets from an ingredient string.

    Args:
        ing (str): Ingredient string

    Returns:
        str: Ingredient string without brackets
    """
    if self.graph_config['STRIP_BRACKETS']:
        prefix = False
        if ing[:2] == '\u2588 ':
            prefix = True
        stripped = ing.split(']')[-1].strip()
        if prefix and stripped[:2] != '\u2588 ':
            stripped = '\u2588 ' + stripped
        return stripped
    else:
        return ing


def check_node_has_port(self: Graph, node: str) -> bool:
    """Checks if the inputted node has a port or not.

    Args:
        node (str): Node string

    Returns:
        bool: Whether or not the inputted node has a port or not
    """
    if node in ['source', 'sink']:
        return True
    if re.match(r'^\d+$', node):
        return True
    return False


def get_output_port_side(self: Graph) -> str:
    """Get output port side depending on graph orientation.

    Returns:
        str: Direction based on graph_config['ORIENTATION']
    """
    dir = self.graph_config['ORIENTATION']
    return {'TB': 's', 'BT': 'n', 'LR': 'e', 'RL': 'w'}.get(dir, 'w')


def get_input_port_side(self: Graph) -> str:
    """Get input port side depending on graph orientation.

    Returns:
        str: Direction based on graph_config['ORIENTATION']
    """
    dir = self.graph_config['ORIENTATION']
    return {'TB': 'n', 'BT': 's', 'LR': 'w', 'RL': 'e'}.get(dir, 'w')


def get_unique_color(self: Graph, id: str) -> str:
    """Returns a unique color from inputted ID.

    Args:
        id (str): Unique ID string. Same ID will return same color

    Returns:
        str: Hex color string
    """
    if id not in self._color_dict:
        self._color_dict[id] = next(self._color_cycler)
    return self._color_dict[id]


def get_port_id(self: Graph, ing_name: str, port_type: str) -> str:
    """Generate a port ID from ing_name and port_type.

    Args:
        ing_name (str): Port ingredient name
        port_type (str): Port type

    Returns:
        str: Port ID
    """
    normal = re.sub(' ', '_', ing_name).lower().strip()
    return f'{port_type}_{normal}'


def get_ing_id(self: Graph, ing_name: str) -> str:
    """Get ingredient ID from ingredient name.

    Args:
        ing_name (str): Ingredient name

    Returns:
        str: Ingredient ID as a string
    """
    id = ing_name
    id = re.sub(r'\[.*?\]', '', id)
    id = id.strip()
    id = re.sub(r' ', '_', id)
    return id.lower()


def get_ing_label(self: Graph, ing_name: str) -> str:
    """Returns a string from an ingredient name into a title. Only exception is EU.

    Args:
        ing_name (str): Ingredient name

    Returns:
        str: Ingredient name as a title
    """
    capitalization_exceptions = {
        'eu': 'EU',
    }
    ing_id = self.get_ing_id(ing_name)
    if ing_id in capitalization_exceptions:
        return capitalization_exceptions[ing_id]
    else:
        return ing_name.title()


def get_quant_label(self: Graph, ing_id: str, ing_quant: float | int) -> str:
    """Get quantity label from ingredient ID and ingredient quantity.

    Args:
        ing_id (str): Ingredient ID as a string
        ing_quant (float | int): Ingredient quantity

    Returns:
        str: Quantity label string
    """
    unit_exceptions = {
        'eu': lambda eu: f'{int(math.floor(eu / 20))}/t'
    }
    if ing_id in unit_exceptions:
        return unit_exceptions[ing_id](ing_quant)
    else:
        return f'{self.round_readable(ing_quant)}/s'


def _combine_outputs(self: Graph):
    """Creates a meta-node on the Graph to combine outputs."""
    ings = defaultdict(list)
    for src, dst, ing in self.edges.keys():
        ings[(src, ing)].append(dst)
    merge = {k: v for k, v in ings.items() if len(v) > 1}

    n = 0
    for t, lst in merge.items():
        src, ing = t

        joint_id = f'joint_o_{n}'
        n = n + 1

        ing_id = self.get_ing_id(ing)
        ing_color = self.get_unique_color(ing_id)
        self.add_node(joint_id, shape='point', color=ing_color)
        q_sum = 0
        for dst in lst:
            k = (src, dst, ing)
            info = self.edges[k]
            self.edges.pop(k)
            quant = info['quant']
            kwargs = info['kwargs']
            q_sum = q_sum + quant
            self.add_edge(joint_id, dst, ing, quant, **kwargs)

        self.add_edge(src, joint_id, ing, q_sum)


def _combine_inputs(self: Graph):
    """Creates a meta-node on the Graphto combine inputs."""
    ings = defaultdict(list)
    for src, dst, ing in self.edges.keys():
        ings[(dst, ing)].append(src)
    merge = {k: v for k, v in ings.items() if len(v) > 1}

    n = 0
    for t, lst in merge.items():
        dst, ing = t

        joint_id = f'joint_i_{n}'
        n = n + 1

        ing_id = self.get_ing_id(ing)
        ing_color = self.get_unique_color(ing_id)
        self.add_node(joint_id, shape='point', color=ing_color)
        q_sum = 0
        for src in lst:
            k = (src, dst, ing)
            info = self.edges[k]
            self.edges.pop(k)
            quant = info['quant']
            kwargs = info['kwargs']
            q_sum = q_sum + quant
            self.add_edge(src, joint_id, ing, quant, **kwargs)

        self.add_edge(joint_id, dst, ing, q_sum)
