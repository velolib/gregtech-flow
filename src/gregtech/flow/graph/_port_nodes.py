import math
import re
from collections import defaultdict

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gregtech.flow.graph import Graph

# This file is for the "port" style nodes
# as designed by Usagirei in https://github.com/OrderedSet86/gtnh-flow/pull/4


def strip_brackets(self: 'Graph', ing: str):
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


def check_node_has_port(self: 'Graph', node):
    if node in ['source', 'sink']:
        return True
    if re.match(r'^\d+$', node):
        return True
    return False


def get_output_port_side(self: 'Graph'):
    dir = self.graph_config['ORIENTATION']
    return {'TB': 's', 'BT': 'n', 'LR': 'e', 'RL': 'w'}.get(dir, 'w')


def get_input_port_side(self: 'Graph'):
    dir = self.graph_config['ORIENTATION']
    return {'TB': 'n', 'BT': 's', 'LR': 'w', 'RL': 'e'}.get(dir, 'w')


def get_unique_color(self: 'Graph', id):
    if id not in self._color_dict:
        self._color_dict[id] = next(self._color_cycler)
    return self._color_dict[id]


def get_port_id(self: 'Graph', ing_name, port_type):
    normal = re.sub(' ', '_', ing_name).lower().strip()
    return f'{port_type}_{normal}'


def get_ing_id(self: 'Graph', ing_name):
    id = ing_name
    id = re.sub(r'\[.*?\]', '', id)
    id = id.strip()
    id = re.sub(r' ', '_', id)
    return id.lower()


def get_ing_label(self: 'Graph', ing_name):
    capitalization_exceptions = {
        'eu': 'EU',
    }
    ing_id = self.get_ing_id(ing_name)
    if ing_id in capitalization_exceptions:
        return capitalization_exceptions[ing_id]
    else:
        return ing_name.title()


def get_quant_label(self: 'Graph', ing_id, ing_quant):
    unit_exceptions = {
        'eu': lambda eu: f'{int(math.floor(eu / 20))}/t'
    }
    if ing_id in unit_exceptions:
        return unit_exceptions[ing_id](ing_quant)
    else:
        return f'{self.userRound(ing_quant)}/s'


def _combine_outputs(self: 'Graph'):
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


def _combine_inputs(self: 'Graph'):
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
