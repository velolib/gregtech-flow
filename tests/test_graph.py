import logging
import os
from pathlib import Path

import pytest
import yaml

from gtnhvelo.data.loadMachines import recipesFromConfig
from gtnhvelo.graph._solver import systemOfEquationsSolverGraphGen
from gtnhvelo.cli import ProgramContext
from gtnhvelo import flow


def generateProjectPaths():
    path_blacklist = [
        Path('circuits/nanocircuits.yaml'),
    ]
    project_paths = (str(pth) for pth in Path('projects/').glob('**/*.yaml') if pth not in path_blacklist
                     if 'dev' not in str(pth))

    return project_paths


@pytest.mark.parametrize("project_name", generateProjectPaths())
def test_lazyGenerateGraphs(project_name):
    pc = ProgramContext(config_path='tests/test_config.yaml')
    recipes = recipesFromConfig(project_name, pc.graph_config, project_folder='')

    path_vars = (os.environ.get('path')).casefold().split(os.pathsep)
    if not [x for x in path_vars if 'graphviz' in x if 'bin' in x]:
        pytest.skip()

    if project_name.endswith('.yaml'):
        project_name = project_name[:-5]

    try:
        systemOfEquationsSolverGraphGen(pc, project_name, recipes, pc.graph_config)
        assert True == True
    except Exception as e:
        assert True == False, f'Failed on {project_name} with error {e}'

@pytest.mark.parametrize("project_name", generateProjectPaths())
def test_flow(project_name):
    project_name = str(Path(project_name).relative_to('projects/'))
    pc = ProgramContext(config_path='tests/test_config.yaml')

    path_vars = (os.environ.get('path')).casefold().split(os.pathsep)
    if not [x for x in path_vars if 'graphviz' in x if 'bin' in x]:
        pytest.skip()

    try:
        flow(project_name, create_dirs=True, config_path='tests/test_config.yaml')
        assert True == True
    except Exception as e:
        assert True == False, f'Failed on {project_name} with error {e}'

if __name__ == '__main__':
    for p in generateProjectPaths():
        print(p)