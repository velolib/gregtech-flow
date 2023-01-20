import logging
import math
from collections import defaultdict
from copy import deepcopy
from string import ascii_uppercase

from gregtech.flow.data.basicTypes import Ingredient, IngredientCollection, Recipe
from gregtech.flow.graph._utils import _iterateOverMachines
from gregtech.flow.gtnh.overclocks import OverclockHandler

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gregtech.flow.graph import Graph


def capitalizeMachine(machine):
    # check if machine has capitals, and if so, preserve them
    capitals = set(ascii_uppercase)
    machine_capitals = [ch for ch in machine if ch in capitals]

    capitalization_exceptions = {
        # Format is old_str: new_str
    }

    if len(machine_capitals) > 0:
        return machine
    elif machine in capitalization_exceptions:
        return capitalization_exceptions[machine]
    else:
        return machine.title()


def createMachineLabels(self: 'Graph'):
    # Distillation Tower
    # ->
    # 5.71x HV Distillation Tower
    # Cycle: 2.0s
    # Amoritized: 1.46K EU/t
    # Per Machine: 256EU/t

    overclock_data = self.parent_context.data['overclock_data']

    for node_id in self.nodes:
        if self._checkIfMachine(node_id):
            rec_id = node_id
            rec = self.recipes[rec_id]
        else:
            continue

        label_lines = []

        # Standard label

        default_label = [
            f'{round(rec.multiplier, 2)}x {rec.user_voltage.upper()} {capitalizeMachine(rec.machine)}',
            f'Cycle: {rec.dur/20}s',
            f'Amoritized: {self.userRound(int(round(rec.eut, 0)))} EU/t',
            f'Per Machine: {self.userRound(int(round(rec.base_eut, 0)))} EU/t',
        ]

        label_lines.extend(default_label)

        if self.graph_config['POWER_UNITS'] != 'eut':
            if self.graph_config['POWER_UNITS'] == 'auto':
                tier_idx = overclock_data['voltage_data']['tiers'].index(rec.user_voltage)
            else:
                tier_idx = overclock_data['voltage_data']['tiers'].index(self.graph_config['POWER_UNITS'])
            voltage_at_tier = self.tierToVoltage(tier_idx)
            label_lines[-2] = f'Amoritized: {self.userRound(int(round(rec.eut, 0)) / voltage_at_tier)} {overclock_data["voltage_data"]["tiers"][tier_idx].upper()}'
            label_lines[-1] = f'Per Machine: {self.userRound(int(round(rec.base_eut, 0)) / voltage_at_tier)} {overclock_data["voltage_data"]["tiers"][tier_idx].upper()}'

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


def addUserNodeColor(self: 'Graph'):
    targeted_nodes = [i for i, x in self.recipes.items() if getattr(x, 'target', False) != False]
    numbered_nodes = [i for i, x in self.recipes.items() if getattr(x, 'number', False) != False]
    all_user_nodes = set(targeted_nodes) | set(numbered_nodes)

    for rec_id in all_user_nodes:
        self.nodes[rec_id].update({'fillcolor': self.graph_config['LOCKEDNODE_COLOR']})


def addMachineMultipliers(self: 'Graph'):
    # Compute machine multiplier based on solved ingredient quantities
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


def addPowerLineNodesV2(self: 'Graph'):
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

        if ing_name in known_burnables and not ing_name in self.graph_config['DO_NOT_BURN']:
            self.parent_context.cLog(f'Detected burnable: {ing_name.title()}! Adding to chart.', level=logging.INFO)
            generator_idx, eut_per_cell = known_burnables[ing_name]
            gen_name = generator_names[generator_idx]

            # Add node
            node_idx = f'{highest_node_index}'

            # Burn gen is a singleblock
            def findClosestVoltage(voltage_list, voltage):
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
            gen_voltage = findClosestVoltage(list(available_efficiencies), voltages[highest_voltage])
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
                wasted_fuel=f'{self.userRound(loss_on_singleblock_output)}EU/t/amp',
            )

            produced_eut_s = quant_s / expended_fuel_t * output_eut
            self.parent_context.cLog(
                ''.join([
                    f'Added {gen_voltage} generator burning {quant_s} {ing_name} for '
                    f'{self.userRound(produced_eut_s/20)}EU/t at {output_eut}EU/t each.'
                ])
            )

            self.addNode(
                node_idx,
                fillcolor=self.graph_config['NONLOCKEDNODE_COLOR'],
                shape='box'
            )

            # Fix edges to point at said node
            # Edge (old output) -> (generator)
            self.addEdge(
                node_from,
                node_idx,
                ing_name,
                quant_s,
                **edge_data['kwargs'],
            )
            # Edge (generator) -> (EU sink)
            self.addEdge(
                node_idx,
                'sink',
                'EU',
                produced_eut_s,
            )
            # Remove old edge and repopulate adjacency list
            del self.edges[edge]
            self.createAdjacencyList()

            highest_node_index += 1


def addSummaryNode(self: 'Graph'):
    # Now that tree is fully locked, add I/O node
    # Specifically, inputs are adj[source] and outputs are adj[sink]
    misc_data = self.parent_context.data['special_machine_weights']
    overclock_data = self.parent_context.data['overclock_data']

    color_positive = self.graph_config['POSITIVE_COLOR']
    color_negative = self.graph_config['NEGATIVE_COLOR']

    def makeLineHtml(lab_text, amt_text, lab_color, amt_color, unit=None):
        if not unit:
            unit = ''
        return ''.join([
            '<tr>'
            f'<td align="left"><font color="{lab_color}" face="{self.graph_config["SUMMARY_FONT"]}">{self.stripBrackets(lab_text)}</font></td>'
            f'<td align ="right"><font color="{amt_color}" face="{self.graph_config["SUMMARY_FONT"]}">{amt_text}{unit}</font></td>'
            '</tr>'
        ])

    self.createAdjacencyList()

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
        else:
            raise NotImplementedError(f'How did this happen? Invalid direction: {direction}')

        for edge in edges:
            _, _, ing_name = edge
            edge_data = self.edges[edge]
            quant = edge_data['quant']

            ing_id = self.getIngId(ing_name)

            ing_names[ing_id] = self.getIngLabel(ing_name)
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

        amt_text = self.getQuantLabel(id, quant)
        name_text = '\u2588 ' + ing_names[id]
        num_color = color_positive if quant >= 0 else color_negative
        ing_color = self.getUniqueColor(id)
        io_label_lines.append(makeLineHtml(name_text, amt_text, ing_color, num_color))

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
    voltage_at_tier = self.tierToVoltage(max_tier)

    # TODO: Clean this up somehhow. So unreadable
    match self.graph_config['POWER_UNITS']:
        case 'auto':
            def fun(z): return self.userRound(z / voltage_at_tier)
            unit = f' {tiers[max_tier].upper()}'
        case 'eut':
            unit = ''
            fun = self.userRound
        case _:
            def fun(z): return self.userRound(z / self.tierToVoltage(tiers.index(self.graph_config['POWER_UNITS'])))
            unit = f' {self.graph_config["POWER_UNITS"].upper()}'

    io_label_lines.append(makeLineHtml('Input EU/t:', fun(eut_rounded), 'white', color_negative, unit))
    if 'eu' in total_io:
        produced_eut = int(math.floor(total_io['eu'] / 20))
        io_label_lines.append(makeLineHtml('Output EU/t:', fun(produced_eut), 'white', color_positive, unit))
        net_eut = produced_eut + eut_rounded
        amt_color = color_positive if net_eut >= 0 else color_negative
        io_label_lines.append(makeLineHtml('Net EU/t:', fun(net_eut), 'white', amt_color, unit))
        io_label_lines.append('<hr/>')

    # Add total machine multiplier count for renewables spreadsheet numbers
    special_machine_weights = misc_data
    sumval = 0
    for rec_id in self.nodes:
        if rec_id in ['source', 'sink']:
            continue
        elif rec_id.startswith('power_'):
            continue
        rec = self.recipes[rec_id]

        machine_weight = rec.multiplier
        if rec.machine in special_machine_weights:
            machine_weight *= special_machine_weights[rec.machine]
        sumval += machine_weight

    io_label_lines.append(makeLineHtml('Total machine count:', self.userRound(sumval), 'white', color_positive))

    # Add peak power load in maximum voltage on chart
    # Compute maximum draw
    max_draw = 0
    for rec in self.recipes.values():
        max_draw += rec.base_eut * math.ceil(rec.multiplier)

    io_label_lines.append(
        makeLineHtml(
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
    self.addNode(
        'total_io_node',
        label=io_label,
        color=self.graph_config['SUMMARY_COLOR'],
        fillcolor=self.graph_config['BACKGROUND_COLOR'],
        shape='box'
    )


def bottleneckPrint(self: 'Graph'):
    # Prints bottlenecks normalized to an input voltage.
    machine_recipes = [x for x in _iterateOverMachines(self)]
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
        raise NotImplementedError()  # FIXME: Add negative overclocking
        for i, rec in enumerate(self.recipes):
            rec.user_voltage = chosen_voltage

            self.recipes[i] = oh.overclockRecipe(rec)
            rec.base_eut = rec.eut

    # Print actual bottlenecks
    for i, rec in zip(range(number_to_print), machine_recipes):
        self.parent_context.cLog(f'{round(rec.multiplier, 2)}x {rec.user_voltage} {rec.machine}', logging.INFO)
        for out in rec.O:
            self.parent_context.cLog(f'    {out.name.title()} ({round(out.quant, 2)})', logging.INFO)
