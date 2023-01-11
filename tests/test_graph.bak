import pytest
import yaml

from gtnhvelo.data.loadMachines import recipesFromConfig
from gtnhvelo.graph import Graph
from gtnhvelo.cli import ProgramContext

pc = ProgramContext()

import json
def loadTestConfig():
    with open('config_factory_graph.yaml', 'r') as f:
        graph_config = yaml.safe_load(f)
    return graph_config

# Note that recipe ordering is deterministic!
# (Thanks to the OrderedDict hook in dataClasses.load.recipesFromConfig)


def test_connectionSimple():
    project_name = 'simpleGraph.yaml'

    # Load recipes
    recipes = recipesFromConfig(project_name, loadTestConfig(), project_folder='tests/testProjects')

    # Create graph
    g = Graph(project_name, recipes, pc, graph_config=loadTestConfig())
    g.connectGraph()

    ### Check connections
    # 0: electrolyzer
    # 1: extractor

    expected_edges = [
        ('source', '1', 'sugar beet'),
        ('1', '0', 'sugar'),
        ('0', 'sink', 'carbon dust'),
        ('0', 'sink', 'oxygen'),
        ('0', 'sink', 'water'),
    ]

    assert set(expected_edges) == set(g.edges.keys())


def test_connectionLoop():
    project_name = 'loopGraph.yaml'

    # Load recipes
    recipes = recipesFromConfig(project_name, loadTestConfig(), project_folder='tests/testProjects')

    # Create graph
    g = Graph(project_name, recipes, pc, graph_config=loadTestConfig())
    g.connectGraph()
    g.removeBackEdges()

    ### Check connections
    # 0: distillation tower
    # 1: large chemical reactor

    expected_edges = [
        ('source', '1', 'acetic acid'),
        ('source', '1', 'sulfuric acid'),
        ('1', '0', 'diluted sulfuric acid'),
        ('1', 'sink', 'ethenone'),
        ('0', 'sink', 'sulfuric acid'),
        ('0', 'sink', 'water'),
    ]

    assert set(expected_edges) == set(g.edges.keys())
