# In theory solving the machine flow as a linear program is fast and simple -
# this prototype explores this.
from __future__ import annotations

import logging
import typing
from collections import Counter, deque
from math import isclose
from typing import TYPE_CHECKING, Callable

from rich.progress import Progress
from sympy import linsolve, symbols
from sympy.sets.sets import EmptySet
from sympy.solvers import solve

from gregtech.flow.exceptions import SolverError
from gregtech.flow.graph import Graph
from gregtech.flow.graph._output import graphviz_output
from gregtech.flow.graph._post_processing import (add_powerline_nodes,
                                                  add_recipe_multipliers,
                                                  add_summary_node,
                                                  add_user_node_color,
                                                  create_machine_labels)
from gregtech.flow.graph._pre_processing import (connect_graph,
                                                 remove_back_edges)

if TYPE_CHECKING:
    from pathlib import Path

    from gregtech.flow.cli import ProgramContext


class SympySolver:
    """Sympy solver for GT: Flow calculations."""

    def __init__(self, graph: Graph) -> None:
        """Initializes SympySolver.

        Args:
            graph (Graph): Graph object
        """
        self.graph = graph
        self.variables: list = []
        self.variable_idx_counter = 0  # Autogen current "head" index for variable number
        self.num_variables = 0  # Expected number of variables - if this diverges from vic, something broke
        self.system: list = []
        self.solved_vars: list = []  # Result from linear solver

        # TODO: Look into merging lookup and edge_from_perspective_to_index - they describe mostly the same thing
        # (machine, product, direction, multi_idx) -> variable index
        self.lookup: dict[tuple[str, str, typing.Literal['I', 'O'] | str, int], int] = {}
        # (edge, machine_id) -> variable index
        self.edge_from_perspective_to_index: dict[tuple, int] = {}

    def array_index(self, rec_id: str, product: str,
                    direction: str, multi_idx: int = 0) -> int:
        """Gets a variable index from self.lookup, else generates unique key.

        Args:
            machine (str): Recipe ID
            product (str): Product of the machine
            direction (str): Direction, either I or O.
            multi_idx (int, optional): Multi index. Defaults to 0.

        Returns:
            int: Variable index
        """
        key = (rec_id, product, direction, multi_idx)
        if key not in self.lookup:
            # print(f'Unique key {key}')
            self.lookup[key] = self.variable_idx_counter
            self.variable_idx_counter += 1
            return self.variable_idx_counter - 1
        else:
            return self.lookup[key]

    def run(self, progress_cb: Callable) -> None:
        """Runs the solver.

        Args:
            progress_cb (Callable): Progress callback for rich Progress object
        """
        self._create_variables()  # initialize v1, v2, v3 ... (first pass)
        progress_cb(6.6)

        # Construct system of equations
        self._add_userlocking()  # add known equations from user "number" and "target" args
        progress_cb(6.6)
        self._add_machine_internal_locking()  # add relations inside machines - eg 1000 wood tar -> 350 benzene
        progress_cb(6.6)
        self._populate_efpti()  # construct "edge_from_perspective_to_index" - a useful index lookup for next steps
        progress_cb(6.6)
        self._add_machinemachine_edges()  # add equations between machines, including complex situations - eg multi IO
        progress_cb(6.6)

        # Solve and if unsolvable, adjust until it is
        self._solve()
        progress_cb(6.6)

        self._write_quants_to_graph()
        progress_cb(6.6)

    def _create_variables(self) -> None:
        """Computes number of variables."""
        num_variables = 0
        for rec_id in self.graph.nodes:
            if self.graph._machine_check(rec_id):
                rec = self.graph.recipes[rec_id]
                # one for each input/output ingredient
                num_variables += len(rec.I) + len(rec.O)
        self.num_variables = num_variables

        symbols_str = ', '.join(['v' + str(x) for x in range(num_variables)])
        self.variables = list(symbols(symbols_str, positive=True, real=True))

    def _add_userlocking(self) -> None:
        """Adds user-determined locked inputs."""
        targeted_nodes = [i for i, x in self.graph.recipes.items(
        ) if getattr(x, 'target', False) is not False]
        numbered_nodes = [i for i, x in self.graph.recipes.items(
        ) if getattr(x, 'number', False) is not False]

        ln = len(numbered_nodes)
        lt = len(targeted_nodes)

        if lt == 0 and ln == 0:
            raise SolverError(
                'Need at least one "number" or "target" argument to base machine balancing around.')

        elif ln != 0 or lt != 0:
            # Add numbered nodes
            for rec_id in numbered_nodes:
                rec = self.graph.recipes[rec_id]

                # Pick a random ingredient to be the "solved" one, then solve for it based
                # on machine number
                if len(rec.I):
                    core_ing = rec.I[0]
                    core_direction = 'I'
                elif len(rec.O):
                    core_ing = rec.O[0]
                    core_direction = 'O'
                else:
                    raise SolverError(f'{rec} has no inputs or outputs!')

                # Solve for ingredient quantity and add to system of equations
                solved_quant_s = core_ing.quant * rec.number / (rec.dur / 20)
                self.system.append(
                    self.variables[self.array_index(rec_id, core_ing.name, core_direction)]
                    -
                    solved_quant_s
                )

            # Add targetted nodes
            for rec_id in targeted_nodes:
                rec = self.graph.recipes[rec_id]
                if len(rec.target) > 1:
                    raise NotImplementedError(
                        'Currently only one targeted ingredient per machine - feel free to open Github ticket')
                target_ingredient = list(rec.target)[0]
                target_quant = rec.target[target_ingredient]

                # Look up the exact ingredient and add the constant to the system of equations
                for ing_direction in ['I', 'O']:
                    directional_matches = [x.name for x in getattr(
                        rec, ing_direction)._ings if x.name == target_ingredient]

                    if directional_matches:
                        ing_name = directional_matches[0]
                        self.system.append(
                            self.variables[self.array_index(rec_id, ing_name, ing_direction)]
                            -
                            target_quant
                        )
                        break
                else:
                    raise SolverError(f'Targetted quantity must be in machine I/O for \n{rec}')

    def _add_machine_internal_locking(self) -> None:
        """Add machine equations.

        Raises:
            RuntimeError: {rec} has no inputs or outputs!
        """
        for rec_id in self.graph.nodes:
            if self.graph._machine_check(rec_id):
                rec = self.graph.recipes[rec_id]

                # Pick a single ingredient to represent the rest of the equations (to
                # avoid having more equations than needed)
                if len(rec.I):
                    core_ing = rec.I[0]
                    core_direction = 'I'
                elif len(rec.O):
                    core_ing = rec.O[0]
                    core_direction = 'O'
                else:
                    raise SolverError(f'{rec} has no inputs or outputs!')

                # Add equations in form of core_ingredient
                for ing_direction in ['I', 'O']:
                    for ing in getattr(rec, ing_direction):
                        if ing.name != core_ing.name:
                            # Determine constant multiple between products
                            multiple = core_ing.quant / ing.quant
                            self.system.append(
                                self.variables[self.array_index(
                                    rec_id, core_ing.name, core_direction)]
                                -
                                multiple *
                                self.variables[self.array_index(rec_id, ing.name, ing_direction)]
                            )

    def _populate_efpti(self):
        """Populates edge_from_perspective_to_index for all edges - so there's something consistent to call for all edges."""
        for edge in self.graph.edges:
            a, b, product = edge

            if self.graph._machine_check(a) and (
                    (edge, a) not in self.edge_from_perspective_to_index):
                self.edge_from_perspective_to_index[(edge, a)] = self.array_index(a, product, 'O')

            if self.graph._machine_check(b) and (
                    (edge, b) not in self.edge_from_perspective_to_index):
                self.edge_from_perspective_to_index[(edge, b)] = self.array_index(b, product, 'I')

    def _add_machinemachine_edges(self):
        """Adds machine-machine edges."""
        # Need to be careful about how these are added - multi input and multi output can
        #   require arbitrarily many variables per equation
        # See https://github.com/OrderedSet86/gtnh-flow/issues/7#issuecomment-1331312996 for an example
        # Solution is below the linked comment
        computed_edges = set()
        for edge in self.graph.edges:
            if edge in computed_edges:
                continue
            a, b, product = edge
            if self.graph._machine_check(a) and self.graph._machine_check(b):
                # print(f'Machine edge detected! {edge}')

                # Run DFS to find all connected machine-machine edges using the same product
                involved_machines = Counter()
                involved_edges = set()
                q = [edge]
                while q:
                    dfs_edge = q.pop()
                    if dfs_edge in involved_edges:
                        continue
                    dfs_a, dfs_b, _ = dfs_edge

                    involved_edges.add(dfs_edge)
                    involved_machines[dfs_a] += 1
                    involved_machines[dfs_b] += 1

                    # Check for all adjacent I/O edges using the same product
                    for edge in self.graph.adj[a]['O']:  # Multi-output
                        if edge[2] == product:
                            q.append(edge)
                    for edge in self.graph.adj[b]['I']:  # Multi-input
                        if edge[2] == product:
                            q.append(edge)

                if len(involved_edges) == 1:
                    # Simple version - all A output fulfills all B input

                    self.system.append(
                        self.variables[self.array_index(a, product, 'O')]
                        -
                        self.variables[self.array_index(b, product, 'I')]
                    )
                else:
                    # Hard version - A and B fulfill some percentage of each other and other machines in a network
                    # Each multi-input and multi-output will require the creation of minimum 2 new variables
                    # print(involved_machines)
                    # print(involved_edges)

                    # Assume no loops since DAG was enforced earlier
                    for rec_id, count in involved_machines.most_common(
                    ):  # most_common so multi-IO variables are created first
                        if count > 1:
                            # Multi-input or multi-output
                            # Old variable is now the collected amount for that side
                            # Then, add new variable for each input/output (minimum 2)

                            relevant_edge = None
                            destinations = []
                            for edge in involved_edges:
                                multi_a, multi_b, multi_product = edge
                                if rec_id in edge[:2]:
                                    if relevant_edge is None:
                                        relevant_edge = edge
                                    if multi_a == rec_id:
                                        destinations.append(multi_b)
                                    elif multi_b == rec_id:
                                        destinations.append(multi_a)

                            self._add_multiequations_on_edge(relevant_edge, rec_id, destinations)

                        else:
                            # Still "simple" - can keep old self.graph variable, but opposite end of
                            # edge must point at correct multi-IO variable

                            # print('Pre-efpti')
                            # for k, v in edge_from_perspective_to_index.items():
                            #     print(k, v)
                            # print()

                            # Figure out if simple machine is a or b
                            for edge in involved_edges:
                                if rec_id in edge[:2]:
                                    relevant_edge = edge

                            a, b, product = relevant_edge

                            # Add equation
                            # for k, v in edge_from_perspective_to_index:
                            #     print(k, v)
                            # print()

                            if rec_id == a:  # a is simple machine
                                multi_idx = self.edge_from_perspective_to_index[(relevant_edge, b)]
                                # print(relevant_edge, rec_id, flush=True)
                                self.system.append(
                                    self.variables[self.array_index(a, product, 'O')]
                                    -
                                    self.variables[self.array_index(
                                        b, product, 'I', multi_idx=multi_idx)]
                                )
                            elif rec_id == b:  # b is simple machine
                                multi_idx = self.edge_from_perspective_to_index[(relevant_edge, a)]
                                self.system.append(
                                    self.variables[self.array_index(
                                        a, product, 'O', multi_idx=multi_idx)]
                                    -
                                    self.variables[self.array_index(b, product, 'I')]
                                )

                computed_edges.update(involved_edges)

    def _add_multiequations_on_edge(self, multi_edge, multi_machine, destinations):
        # TODO: Docstring
        # destinations = list of nodes

        multi_a, multi_b, multi_product = multi_edge
        if multi_machine == multi_a:
            direction = 'O'
        elif multi_machine == multi_b:
            direction = 'I'

        # Add new variables vX, vY, ...
        new_symbols = ', '.join(['v' + str(x + self.num_variables)
                                for x in range(len(destinations))])
        self.variables.extend(list(symbols(new_symbols, positive=True, real=True)))

        # Look up old variable association with edge
        old_var = self.edge_from_perspective_to_index[(multi_edge, multi_machine)]
        # print(old_var)

        # Check for existing edge equations involving old_var in system and remove if exist
        # TODO: (ignoring this for now because it's not relevant for _addMachineMachineEdges)
        # Consider keeping the machine-internal equation - it will remain accurate
        # as the old var is kept for it

        # Update efpti and arrayIndex for new variables + edges
        connected_edges = self.graph.adj[multi_machine][direction]
        variable_index = self.num_variables
        for edge in connected_edges:
            a, b, product = edge
            if product != multi_product:
                continue

            self.edge_from_perspective_to_index[(edge, multi_machine)] = variable_index
            # Sanity check that variable counts match
            self.array_index(multi_machine, product, direction, multi_idx=variable_index)
            variable_index += 1

        if direction == 'O':
            self.graph.parent_context.log(
                f'Solving multi-output scenario involving {multi_product}!', level=logging.INFO)
        elif direction == 'I':
            self.graph.parent_context.log(
                f'Solving multi-input scenario involving {multi_product}!', level=logging.INFO)

        # Add new equations for multi-IO
        # print(self.variables)
        # for k,v in self.lookup.items():
        #     print(k, v)

        base = self.variables[self.array_index(
            multi_machine, multi_product, direction, multi_idx=0)]
        for i, _dst in enumerate(destinations):
            base -= self.variables[self.array_index(multi_machine,
                                                    multi_product, direction, multi_idx=self.num_variables + i)]
        self.system.append(base)

        self.num_variables += len(destinations)

    def _solve(self) -> None:
        """Loops solving until solved. Algorithm may adjust edges each time it sees an EmptySet.

        Raises:
            NotImplementedError: Multiple solutions - no code written to deal with this scenario yet
        """
        while True:
            res = linsolve(self.system, self.variables)
            # print(res)
            if isinstance(res, EmptySet):
                self._inconsistency_search()
                exit(1)
            else:
                break

        lstres = list(res)
        if len(lstres) > 1:
            raise NotImplementedError(
                'Multiple solutions - no code written to deal with this scenario yet')
        self.solved_vars = res.args[0]

    def _inconsistency_search(self) -> None:
        """Solves each equation stepwise until inconsistency is found, then report to end user."""
        self.graph.parent_context.log(
            'Searching for inconsistency in system of equations...', level=logging.INFO)

        # for expr in system:
        #     print(expr)
        # print()

        equations_to_check = deque(self.system)
        max_iter = len(self.system) ** 2 + 1
        iterations = 0

        solved_values: dict = {}
        inconsistent_variables = []

        while equations_to_check and iterations < max_iter:
            expr = equations_to_check.popleft()

            # Detect variable or variables in equation
            involved_variables = expr.as_terms()[-1]

            # Solve if feasible, otherwise go to next
            # Can be solved if only 1 unknown variable
            unsolved = [x for x in involved_variables if x not in solved_values]
            solved = [x for x in involved_variables if x in solved_values]

            if len(unsolved) <= 1:
                for var in solved:
                    expr = expr.subs(var, solved_values[var])
                # print('   ', expr)

                # If expr is a nonzero constant, inconsistency is found
                if expr.is_constant():
                    constant_diff = float(expr)
                    if not isclose(constant_diff, 0.0, abs_tol=0.00000001):
                        # self.graph.parent_context.log(f'Inconsistency found in {preexpr}!', level=logging.WARNING)
                        # Now print what the variables are referring to and output debug graph
                        inconsistent_variables.append((involved_variables, constant_diff))
                        iterations += 1
                        continue

                unvar = unsolved[0]
                solution = solve(expr, unvar)

                if len(unsolved) == 1:
                    if len(solution) == 1:
                        sval = solution[0]
                        solved_values[unvar] = sval
                        # print(sval)
                    else:
                        raise NotImplementedError(f'{solution=}')
                else:
                    raise NotImplementedError(
                        f'{expr} {sorted(solved_values.items(), key=lambda tup: str(tup[0]))}')

            else:
                equations_to_check.append(expr)

            iterations += 1

        if inconsistent_variables == []:
            raise SolverError(
                'Both linear and nonlinear solver found empty set, so system of equations has no solutions -- report to dev.')

        # Check inconsistent equations to see if products on both sides are the
        # same - these are the core issues
        def var_to_idx(var):
            return int(str(var).strip('v'))

        # for k, v in edge_from_perspective_to_index.items():
        #     print(k, v)

        idx_to_mpdm = {idx: mpdm for mpdm, idx in self.lookup.items()}
        for group, _constant_diff in inconsistent_variables:
            assert len(group) == 2  # TODO: NotImplemented

            # Reverse lookup using var
            products = set()
            mpdm_cache = []
            for var in group:
                idx = var_to_idx(var)
                mpdm = idx_to_mpdm[idx]
                mpdm_cache.append(mpdm)
                machine, product, direction, multi_idx = mpdm
                products.add(product)

            # When problematic inconsistency is found...
            if len(products) == 1:
                self.graph.parent_context.log(
                    f'Major inconsistency: {group}', level=logging.WARNING)

                self.graph.parent_context.log(
                    f'Between output={self.graph.recipes[mpdm_cache[0][0]].O}', level=logging.WARNING)
                self.graph.parent_context.log(
                    f'    and  input={self.graph.recipes[mpdm_cache[1][0]].I}', level=logging.WARNING)

                self.graph.parent_context.log('Please fix by either:', level=logging.INFO)

                parent_group_idx = 0
                child_group_idx = 1

                # Negative means too much of right side, or too few of other sided inputs
                self.graph.parent_context.log(
                    f'1. Sending excess {group[parent_group_idx]} {product} to sink', level=logging.INFO)

                # Check other sided inputs
                machine, product, direction, multi_idx = idx_to_mpdm[var_to_idx(
                    group[child_group_idx])]
                nonself_product = []
                for edge in self.graph.adj[machine][direction]:
                    # print(self.graph.adj[machine])
                    # print(edge)
                    a, b, edgeproduct = edge
                    if edgeproduct != product:
                        nonself_product.append((
                            edgeproduct,
                            'v' + f'{self.edge_from_perspective_to_index[(edge, machine)]}',
                        ))

                self.graph.parent_context.log(
                    f'2. Pulling more {nonself_product} from source', level=logging.INFO)

                # Output graph for end user to view
                self._add_vars_to_edges()
                graphviz_output(self.graph)

                # TODO: Automate solution process fully

                # selection = input()  # TODO: Verify input
                selection = 1

                if selection == '1':  # noqa
                    # Send excess to sink
                    # 1. Similar to multi-IO: (a-c could probably be spun off into another fxn)
                    #       a. reassociate old variable with machine sum of product
                    #       b. create a new variable for old edge
                    #       c. create a new variable for machine -> sink
                    # 2. Redo linear solve
                    # 3. Give option for user to add new I/O association to YAML config (will
                    # delete comments)
                    pass
                elif selection == '2':  # noqa
                    # Pull more of each other input from source
                    # 1. Similar to multi-IO: (a-c could probably be spun off into another fxn)
                    #       a. reassociate each old variable on all sides of machine with machine sum of product
                    #       b. create a new variable for each old edge
                    #       c. create a new variable for each source -> machine
                    # 2. Redo linear solve
                    # 3. Give option for user to add new I/O association to YAML config (will
                    # delete comments)
                    pass

    def _add_vars_to_edges(self) -> None:
        # Add variable indices to edges and rec_id to machines

        # Lookup is a dictionary defined like this:
        #   def arrayIndex(machine, product, direction):
        # Edges in self.edges are defined like:
        #   rec_id_a, rec_id_b, product

        for edge_perspective_data, variable_idx in self.edge_from_perspective_to_index.items():
            edge, perspective = edge_perspective_data
            a, b, product = edge

            if 'debugHead' not in self.graph.edges[edge]:
                self.graph.edges[edge]['debugHead'] = ''
            if 'debugTail' not in self.graph.edges[edge]:
                self.graph.edges[edge]['debugTail'] = ''

            if perspective == b:
                self.graph.edges[edge]['debugHead'] += f'v{variable_idx}'
            elif perspective == a:
                self.graph.edges[edge]['debugTail'] += f'v{variable_idx}'

        for node_id in self.graph.nodes:
            if self.graph._machine_check(node_id):
                rec_id = node_id
                rec = self.graph.recipes[rec_id]
            else:
                continue

            self.graph.nodes[rec_id]['label'] = f'[id:{rec_id}] {rec.machine}'

    def _write_quants_to_graph(self) -> None:
        """Updates graph edge values."""
        for edge in self.graph.edges:
            a, b, product = edge
            a_machine = self.graph._machine_check(a)
            b_machine = self.graph._machine_check(b)

            if a_machine and b_machine:
                # Sanity check both edges and make sure they match
                a_index = self.edge_from_perspective_to_index[(edge, a)]
                b_index = self.edge_from_perspective_to_index[(edge, b)]

                a_quant = self.solved_vars[a_index]
                b_quant = self.solved_vars[b_index]

                if isclose(a_quant, b_quant, rel_tol=0.05):
                    relevant_edge = self.graph.edges[edge]
                    relevant_edge['quant'] = float(a_quant)
                    relevant_edge['locked'] = True  # TODO: Legacy - check if can be removed
                else:
                    raise SolverError('\n'.join([
                        'Mismatched machine-edge quantities:',
                        f'{a_quant}',
                        f'{b_quant}',
                    ]))

            elif a_machine or b_machine:
                # Assume a_machine for now
                if a_machine:
                    solution_index = self.edge_from_perspective_to_index[(edge, a)]
                elif b_machine:
                    solution_index = self.edge_from_perspective_to_index[(edge, b)]

                quant = self.solved_vars[solution_index]
                relevant_edge = self.graph.edges[edge]
                relevant_edge['quant'] = float(quant)
                relevant_edge['locked'] = True  # TODO: Legacy - check if can be removed


def preprocess_graph(self: Graph, progress_cb) -> None:
    """Graph pre-processing.

    Args:
        self (Graph): Graph object
        progress_cb (Callable): Progress callback for rich Progress object
    """
    connect_graph(self)
    progress_cb(6.6)
    remove_back_edges(self)
    progress_cb(6.6)
    self.create_adjacency_list()
    progress_cb(6.6)


def postprocess_graph(self: Graph, progress_cb: Callable) -> None:
    """Graph post-processing.

    Args:
        self (Graph): Graph object
        progress_cb (Callable): Progress callback for rich Progress object
    """
    if self.graph_config.get('POWER_LINE', False):
        add_powerline_nodes(self)

    add_recipe_multipliers(self)
    progress_cb(6.6)
    create_machine_labels(self)
    progress_cb(6.6)
    add_summary_node(self)
    progress_cb(6.6)
    add_user_node_color(self)
    progress_cb(6.6)

    if self.graph_config.get('COMBINE_INPUTS', False):
        self._combine_inputs()
    if self.graph_config.get('COMBINE_OUTPUTS', False):
        self._combine_outputs()
    progress_cb(6.6)


def equations_solver(self: ProgramContext, project_name: str | Path,
                     recipes: list, title: str = '') -> None:
    """Runs the equations solver and outputs a graph.

    Args:
        self (ProgramContext): ProgramContext object
        project_name (str): Project name as a string
        recipes (list): Recipes list
        title (str, optional): Graph title. Defaults to None.
    """
    project_name = str(project_name)
    with Progress(disable=bool(self.quiet), transient=True) as progress:
        task = progress.add_task(f'[cyan]{project_name}', total=100)

        def update_progress(advance: float):
            return progress.update(task, advance=advance)
        g = Graph(project_name, recipes, self, title=title)

        preprocess_graph(g, update_progress)

        g.parent_context.log('Running linear solver...', level=logging.INFO)
        solver = SympySolver(g)
        solver.run(update_progress)

        postprocess_graph(g, update_progress)
        graphviz_output(g)
        update_progress(100)
        progress.stop()
