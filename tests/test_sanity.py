import logging
import os
from pathlib import Path

import pytest
import yaml

from gtnhvelo.data.loadMachines import recipesFromConfig
from gtnhvelo.graph._solver import systemOfEquationsSolverGraphGen
from gtnhvelo.cli import ProgramContext


def generateProjectPaths():
    path_blacklist = [
        Path('circuits/nanocircuits.yaml'),
    ]
    project_paths = (str(pth) for pth in Path('projects/').glob('**/*.yaml') if pth not in path_blacklist
                     if 'dev' not in str(pth))

    return project_paths


# def generateProjectPaths():
#     return ['projects/pe/apple.yaml']


@pytest.mark.parametrize("project_name", generateProjectPaths())
def test_lazyGenerateGraphs(project_name):
    """
    Run locally
    """
    pc = ProgramContext(config_path='tests/test_config.yaml')
    recipes = recipesFromConfig(project_name, pc.graph_config, project_folder='')

    if project_name.endswith('.yaml'):
        project_name = project_name[:-5]

    try:
        systemOfEquationsSolverGraphGen(pc, project_name, recipes, pc.graph_config)
        assert True == True
    except Exception as e:
        assert True == False, f'Failed on {project_name} with error {e}'


if __name__ == '__main__':
    for p in generateProjectPaths():
        print(p)