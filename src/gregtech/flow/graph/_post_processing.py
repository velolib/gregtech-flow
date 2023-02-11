from __future__ import annotations

import logging
import math
from collections import defaultdict
from copy import deepcopy
from string import ascii_uppercase
from typing import TYPE_CHECKING

from gregtech.flow.graph._utils import _machine_iterate
from gregtech.flow.gtnh.overclocks import OverclockHandler
from gregtech.flow.recipe.basic_types import (Ingredient, IngredientCollection,
                                              Recipe)

if TYPE_CHECKING:
    from gregtech.flow.graph import Graph


def capitalize_machine(machine: str) -> str:
    """Check if machine string has capitals, and if so, preserve them.

    Args:
        machine (str): Machine name as astring

    Returns:
        str: Capitalized (or not) machine name
    """
    capitals = set(ascii_uppercase)
    machine_capitals = [ch for ch in machine if ch in capitals]

    capitalization_exceptions: dict[str, str] = {
        '': ''  # placeholder
    }

    if len(machine_capitals) > 0:
        return machine
    elif machine in capitalization_exceptions:
        return capitalization_exceptions[machine]
    else:
        return machine.title()


def create_machine_labels(self: Graph) -> None:
    """Creates machine labels for the nodes in this Graph.

    Args:
        self (Graph): Graph object
    """
    overclock_data = self.parent_context.data['overclock_data']

    for node_id in self.nodes:
        if self._machine_check(node_id):
            rec_id = node_id
            rec = self.recipes[rec_id]
        else:
            continue

        label_lines = [
            f'{round(rec.multiplier, 2)}x {rec.user_voltage.upper()} {capitalize_machine(rec.machine)}',
            f'Cycle: {rec.dur/20}s',
            f'Amoritized: {self.round_readable(int(round(rec.eut, 0)))} EU/t',
            f'Per Machine: {self.round_readable(int(round(rec.base_eut, 0)))} EU/t',
        ]

        if self.graph_config['POWER_UNITS'] != 'eut':
            if self.graph_config['POWER_UNITS'] == 'auto':
                tier_idx = overclock_data['voltage_data']['tiers'].index(rec.user_voltage)
            else:
                tier_idx = overclock_data['voltage_data']['tiers'].index(
                    self.graph_config['POWER_UNITS'])
            voltage_at_tier = self.idx_to_voltage(tier_idx)
            label_lines[-2] = f'Amoritized: {self.round_readable(int(round(rec.eut, 0)) / voltage_at_tier)} {overclock_data["voltage_data"]["tiers"][tier_idx].upper()}'
            label_lines[-1] = f'Per Machine: {self.round_readable(int(round(rec.base_eut, 0)) / voltage_at_tier)} {overclock_data["voltage_data"]["tiers"][tier_idx].upper()}'

        # Edits for power machines
        recognized_basic_power_machines = {
            # "basic" here means "doesn't cost energy to run"
            'gas turbine',
            'combustion gen',
            'semifluid gen',
            'steam turbine',
            'rocket engine',

            'large naquadah reactor',
            'large gas turbine',
            'large steam turbine',
            'large combustion engine',
            'extreme combustion engine',
            'XL Turbo Gas Turbine',
            'XL Turbo Steam Turbine',

            'air intake hatch',
        }
        if rec.machine in recognized_basic_power_machines:
            # Remove power input data
            label_lines = label_lines[:-2]

        line_if_attr_exists = {
            'heat': (lambda rec: f'Base Heat: {rec.heat}K'),
            'coils': (lambda rec: f'Coils: {rec.coils.title()}'),
            'saw_type': (lambda rec: f'Saw Type: {rec.saw_type.title()}'),
            'material': (lambda rec: f'Turbine Material: {rec.material.title()}'),
            'size': (lambda rec: f'Size: {rec.size.title()}'),
            'efficiency': (lambda rec: f'Efficiency: {rec.efficiency}'),
            'wasted_fuel': (lambda rec: f'Wasted Fuel: {rec.wasted_fuel}'),
        }
        for lookup, line_generator in line_if_attr_exists.items():
            if hasattr(rec, lookup):
                label_lines.append(line_generator(rec))

        self.nodes[rec_id]['label'] = '\n'.join(label_lines)


def add_user_node_color(self: Graph) -> None:
    """Sets the color of the locked nodes in this Graph.

    Args:
        self (Graph): Graph object
    """
    targeted_nodes = [i for i, x in self.recipes.items(
    ) if getattr(x, 'target', False) is not False]
    numbered_nodes = [i for i, x in self.recipes.items(
    ) if getattr(x, 'number', False) is not False]
    all_user_nodes = set(targeted_nodes) | set(numbered_nodes)

    for rec_id in all_user_nodes:
        self.nodes[rec_id].update({'fillcolor': self.graph_config['LOCKEDNODE_COLOR']})


def add_recipe_multipliers(self: Graph) -> None:
    """Multiplies the Recipes in this Graph using the data from the SympySolver.

    Args:
        self (Graph): Graph object
    """
    # Compute recipe multiplier based on solved ingredient quantities
    # FIXME: If multipliers disagree, sympy solver might have failed on an earlier step

    for rec_id, rec in self.recipes.items():
        multipliers = []

        for io_dir in ['I', 'O']:
            for ing in getattr(rec, io_dir):
                ing_name = ing.name
                base_quant = ing.quant

                # Look up edge value from sympy solver
                solved_quant_per_s = 0
                for edge in self.adj[rec_id][io_dir]:
                    if edge[2] == ing_name:
                        # print(edge, self.edges[edge]['quant'])
                        solved_quant_per_s += self.edges[edge]['quant']

                base_quant_s = base_quant / (rec.dur / 20)

                # print(io_dir, rec_id, ing_name, getattr(rec, io_dir))
                # print(solved_quant_per_s, base_quant_s, rec.dur)
                # print()

                machine_multiplier = solved_quant_per_s / base_quant_s
                multipliers.append(machine_multiplier)

        final_multiplier = max(multipliers)
        rec.multiplier = final_multiplier
        rec.eut = rec.multiplier * rec.eut


def add_powerline_nodes(self: Graph) -> None:
    """Adds power line nodes to this Graph.

    Args:
        self (Graph): Graph object
    """
    generator_names = {
        0: 'gas turbine',
        1: 'combustion gen',
        2: 'semifluid gen',
        3: 'steam turbine',
        4: 'rocket engine',
        5: 'large naquadah reactor',
    }

    power_data = self.parent_context.data['power_data']
    overclock_data = self.parent_context.data['overclock_data']

    turbineables = power_data['turbine_fuels']
    combustables = power_data['combustion_fuels']
    semifluids = power_data['semifluids']
    rocket_fuels = power_data['rocket_fuels']
    naqline_fuels = power_data['naqline_fuels']

    known_burnables = {x: [0, y] for x, y in turbineables.items()}
    known_burnables.update({x: [1, y] for x, y in combustables.items()})
    known_burnables.update({x: [2, y] for x, y in semifluids.items()})
    known_burnables['steam'] = [3, 500]
    known_burnables.update({x: [4, y] for x, y in rocket_fuels.items()})
    known_burnables.update({x: [5, y] for x, y in naqline_fuels.items()})

    # Add new burn machines to graph - they will be computed for using new solver
    # 1. Find highest voltage on the chart - use this for burn generator tier
    # 2. Figure out highest node index on the chart - use this for adding generator nodes
    voltages = overclock_data['voltage_data']['tiers']
    highest_voltage = 0
    highest_node_index = 0
    for rec_id, rec in self.recipes.items():

        rec_voltage = voltages.index(rec.user_voltage)
        if rec_voltage > highest_voltage:
            highest_voltage = rec_voltage

        int_index = int(rec_id)
        if int_index > highest_node_index:
            highest_node_index = int_index

    highest_node_index += 1

    # 3. Redirect burnables currently going to sink and redirect them to a new burn machine
    outputs = self.adj['sink']['I']
    for edge in deepcopy(outputs):
        node_from, _, ing_name = edge
        edge_data = self.edges[edge]
        quant_s = edge_data['quant']

        if (ing_name in known_burnables) and (ing_name not in self.graph_config['DO_NOT_BURN']):
            self.parent_context.log(
                f'Detected burnable: {ing_name.title()}! Adding to chart.', level=logging.INFO)
            generator_idx, eut_per_cell = known_burnables[ing_name]
            gen_name = generator_names[generator_idx]

            # Add node
            node_idx = f'{highest_node_index}'

            # Burn gen is a singleblock
            def find_closest_voltage(voltage_list, voltage):
                nonlocal voltages
                leftmost = voltages.index(voltage_list[0])
                rightmost = voltages.index(voltage_list[-1])
                target = voltages.index(voltage)

                # First try to voltage down
                if rightmost < target:
                    return voltages[rightmost]
                elif leftmost <= target <= rightmost:
                    return voltages[target]
                elif leftmost > target:
                    return voltages[leftmost]

            available_efficiencies = power_data['simple_generator_efficiencies'][gen_name]
            gen_voltage = find_closest_voltage(
                list(available_efficiencies), voltages[highest_voltage])
            efficiency = available_efficiencies[gen_voltage]

            # Compute I/O for a single tick
            gen_voltage_index = voltages.index(gen_voltage)
            output_eut = 32 * (4 ** gen_voltage_index)
            loss_on_singleblock_output = (2 ** (gen_voltage_index + 1))
            expended_eut = output_eut + loss_on_singleblock_output

            expended_fuel_t = expended_eut / (eut_per_cell / 1000 * efficiency)

            gen_input = IngredientCollection(
                Ingredient(
                    ing_name,
                    expended_fuel_t
                )
            )
            gen_output = IngredientCollection(
                Ingredient(
                    'EU',
                    output_eut
                )
            )

            # Append to recipes
            self.recipes[str(highest_node_index)] = Recipe(
                gen_name,
                gen_voltage,
                gen_input,
                gen_output,
                0,
                1,
                efficiency=f'{efficiency*100}%',
                wasted_fuel=f'{self.round_readable(loss_on_singleblock_output)}EU/t/amp',
            )

            produced_eut_s = quant_s / expended_fuel_t * output_eut
            self.parent_context.log(
                ''.join([
                    f'Added {gen_voltage} generator burning {quant_s} {ing_name} for '
                    f'{self.round_readable(produced_eut_s/20)}EU/t at {output_eut}EU/t each.'
                ])
            )

            self.add_node(
                node_idx,
                fillcolor=self.graph_config['NONLOCKEDNODE_COLOR'],
                shape='box'
            )

            # Fix edges to point at said node
            # Edge (old output) -> (generator)
            self.add_edge(
                node_from,
                node_idx,
                ing_name,
                quant_s,
                **edge_data['kwargs'],
            )
            # Edge (generator) -> (EU sink)
            self.add_edge(
                node_idx,
                'sink',
                'EU',
                produced_eut_s,
            )
            # Remove old edge and repopulate adjacency list
            del self.edges[edge]
            self.create_adjacency_list()

            highest_node_index += 1


def add_summary_node(self: Graph) -> None:
    """Create summary node in graph.

    Args:
        self (Graph): Graph object
    """
    # Now that tree is fully locked, add I/O node
    # Specifically, inputs are adj[source] and outputs are adj[sink]
    misc_data = self.parent_context.data['special_machine_weights']
    overclock_data = self.parent_context.data['overclock_data']

    color_positive = self.graph_config['POSITIVE_COLOR']
    color_negative = self.graph_config['NEGATIVE_COLOR']

    def make_html_line(lab_text: str, amt_text: str, lab_color: str,
                       amt_color: str, unit: str = '') -> str:
        """Returns an HTML <tr></tr> element from inputs for the summary.

        Args:
            lab_text (str): Label text
            amt_text (str): Amount text
            lab_color (str): Label color
            amt_color (str): Amount color
            unit (str, optional): Amount text unit. Defaults to None.

        Returns:
            str: HTML <tr></tr> element
        """
        if not unit:
            unit = ''
        return ''.join([
            '<tr>'
            f'<td align="left"><font color="{lab_color}" face="{self.graph_config["SUMMARY_FONT"]}">{self.strip_brackets(lab_text)}</font></td>'
            f'<td align ="right"><font color="{amt_color}" face="{self.graph_config["SUMMARY_FONT"]}">{amt_text}{unit}</font></td>'
            '</tr>'
        ])

    self.create_adjacency_list()

    # Compute I/O
    total_io: dict = defaultdict(float)
    ing_names = defaultdict(str)
    for direction in [-1, 1]:
        if direction == -1:
            # Inputs
            edges = self.adj['source']['O']
        elif direction == 1:
            # Outputs
            edges = self.adj['sink']['I']
        for edge in edges:
            _, _, ing_name = edge
            edge_data = self.edges[edge]
            quant = edge_data['quant']

            ing_id = self.get_ing_id(ing_name)

            ing_names[ing_id] = self.get_ing_label(ing_name)
            total_io[ing_id] += direction * quant

    # Create I/O lines
    io_label_lines = []
    io_label_lines.append(
        f'<tr><td align="left"><font color="white" face="{self.graph_config["SUMMARY_FONT"]}"><b>Summary</b></font></td></tr><hr/>')

    for id, quant in sorted(total_io.items(), key=lambda x: x[1]):
        if id == 'eu':
            continue

        # Skip if too small (intended to avoid floating point issues)
        near_zero_range = 10**-5
        if -near_zero_range < quant < near_zero_range:
            continue

        amt_text = self.get_quant_label(id, quant)
        name_text = '\u2588 ' + ing_names[id]
        num_color = color_positive if quant >= 0 else color_negative
        ing_color = self.get_unique_color(id)
        io_label_lines.append(make_html_line(name_text, amt_text, ing_color, num_color))

    # Compute total EU/t cost and (if power line) output
    total_eut = 0
    for rec in self.recipes.values():
        total_eut += rec.eut
    io_label_lines.append('<hr/>')
    eut_rounded = -int(math.ceil(total_eut))

    # Find maximum voltage
    max_tier = -1
    tiers = overclock_data['voltage_data']['tiers']
    for rec in self.recipes.values():
        tier = tiers.index(rec.user_voltage)
        if tier > max_tier:
            max_tier = tier
    voltage_at_tier = self.idx_to_voltage(max_tier)

    # TODO: Clean this up somehhow. So unreadable
    match self.graph_config['POWER_UNITS']:
        case 'auto':
            def unit_function(z):
                return self.round_readable(z / voltage_at_tier)
            unit = f' {tiers[max_tier].upper()}'
        case 'eut':
            unit = ''
            unit_function = self.round_readable  # noqa
        case _:
            def unit_function(z):
                return self.round_readable(
                    z / self.idx_to_voltage(tiers.index(self.graph_config['POWER_UNITS'])))
            unit = f' {self.graph_config["POWER_UNITS"].upper()}'

    io_label_lines.append(make_html_line(
        'Input EU/t:', unit_function(eut_rounded), 'white', color_negative, unit))
    if 'eu' in total_io:
        produced_eut = int(math.floor(total_io['eu'] / 20))
        io_label_lines.append(make_html_line(
            'Output EU/t:', unit_function(produced_eut), 'white', color_positive, unit))
        net_eut = produced_eut + eut_rounded
        amt_color = color_positive if net_eut >= 0 else color_negative
        io_label_lines.append(make_html_line(
            'Net EU/t:', unit_function(net_eut), 'white', amt_color, unit))
        io_label_lines.append('<hr/>')

    # Add total machine multiplier count for renewables spreadsheet numbers
    special_machine_weights = misc_data
    sumval = 0
    for rec_id in self.nodes:
        if rec_id in ['source', 'sink'] or rec_id.startswith('power_'):
            continue
        rec = self.recipes[rec_id]

        machine_weight = rec.multiplier
        if rec.machine in special_machine_weights:
            machine_weight *= special_machine_weights[rec.machine]
        sumval += machine_weight

    io_label_lines.append(make_html_line('Total machine count:',
                          self.round_readable(sumval), 'white', color_positive))

    # Add peak power load in maximum voltage on chart
    # Compute maximum draw
    max_draw = 0
    for rec in self.recipes.values():
        max_draw += rec.base_eut * math.ceil(rec.multiplier)

    io_label_lines.append(
        make_html_line(
            'Peak power draw:',
            f'{round(max_draw/voltage_at_tier, 2)}A {tiers[max_tier].upper()}',
            'white',
            color_negative
        )
    )

    # Create final table
    io_label = ''.join(io_label_lines)
    io_label = f'<<table border="0">{io_label}</table>>'

    # Add to graph
    self.add_node(
        'total_io_node',
        label=io_label,
        color=self.graph_config['SUMMARY_COLOR'],
        fillcolor=self.graph_config['BACKGROUND_COLOR'],
        shape='box'
    )


def bottleneck_print(self: Graph) -> None:
    """Prints bottlenecks normalized to an input voltage.

    Args:
        self (Graph): Graph object.

    Raises:
        NotImplementedError: Negative overclocking not implemented.
    """
    # Prints bottlenecks normalized to an input voltage.
    machine_recipes = list(_machine_iterate(self))
    machine_recipes.sort(
        key=lambda rec: rec.multiplier,
        reverse=True,
    )

    max_print: int = self.graph_config['MAX_BOTTLENECKS']
    number_to_print = max(len(machine_recipes) // 10, max_print)

    if self.graph_config.get('USE_BOTTLENECK_EXACT_VOLTAGE'):
        # Want to overclock and underclock to force the specific voltage
        chosen_voltage = self.graph_config.get('BOTTLENECK_MIN_VOLTAGE')

        oh = OverclockHandler(self.parent_context)
        # FIXME: Add negative overclocking
        raise NotImplementedError('Negative overclocking not implemented')
        for i, rec in enumerate(self.recipes):
            rec.user_voltage = chosen_voltage

            self.recipes[i] = oh.overclockRecipe(rec)
            rec.base_eut = rec.eut

    # Print actual bottlenecks
    for _i, rec in zip(range(number_to_print), machine_recipes):
        self.parent_context.log(
            f'{round(rec.multiplier, 2)}x {rec.user_voltage} {rec.machine}', logging.INFO)
        for out in rec.O:
            self.parent_context.log(
                f'    {out.name.title()} ({round(out.quant, 2)})', logging.INFO)
