# Tests for _utils.py that are probably not neede

import pytest
from gtnhvelo.graph._utils import swapIO, userRound
import yaml
import pkgutil

from gtnhvelo.data.loadMachines import recipesFromConfig
from gtnhvelo.graph import Graph
from gtnhvelo.cli import ProgramContext

pc = ProgramContext()

import json
def loadTestConfig():
    with open('config_factory_graph.yaml', 'r') as f:
        graph_config = yaml.safe_load(f)
    return graph_config

def test_swapIO():
    _i_ = swapIO('I')
    _o_ = swapIO('O')
    assert _i_ == 'O'
    assert _o_ == 'I'

    with pytest.raises(RuntimeError):
        swapIO('Z')
        swapIO('sonar')

def test_userRound():
    nums = [0.0004, 512, 2_306, 7_777, 2_423_555,
            555_555_555, 2_416_777_876, 5_924_333]
    result = []
    for num in nums:
        result.append(userRound(num))
    assert result == ['0.0', '512', '2.31K', '7.78K', '2.42M',
                      '555.56M', '2.42B', '5.92M']

def test_tierToVoltage():
    project_name = 'simpleGraph.yaml'

    # Load recipes
    recipes = recipesFromConfig(project_name, loadTestConfig(), project_folder='tests/testProjects')

    # Create graph
    g = Graph(project_name, recipes, pc, graph_config=loadTestConfig())

    tiers = yaml.safe_load(pkgutil.get_data('gtnhvelo', 'resources/data.yaml'))['overclock_data']['voltage_data']['tiers']
    tiers_dict = {
        'lv': 32, 'mv': 128, 'hv': 512, 'ev': 2048,
        'iv': 8192, 'luv': 32768, 'zpm': 131072,
        'uv': 524288, 'uhv': 2097152, 'uev': 8388608,
        'uiv': 33554432, 'umv': 134217728, 'uxv': 536870912,
        }
    for tier, voltage in tiers_dict.items():
        tier_idx = tiers.index(tier)
        ttv = g.tierToVoltage(tier_idx)
        assert voltage == ttv