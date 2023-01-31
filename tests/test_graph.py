# flake8: noqa
import sys
from pathlib import Path
from functools import lru_cache

import pytest

from gregtech.flow.data.loadMachines import load_recipes
from gregtech.flow.graph._solver import equations_solver
from gregtech.flow.cli import ProgramContext
from gregtech.flow import flow

@lru_cache(1)
def get_os_config():
    match sys.platform:
        case 'linux':
            return 'tests/test_config_linux.yaml'
        case 'win32':
            return 'tests/test_config_windows.yaml'
        case _:
            raise NotImplementedError(f'Invalid OS for testing: "{sys.platform}", contact dev for implementation!')

def generateProjectPaths():
    path_blacklist = [
        Path('circuits/nanocircuits.yaml'),
    ]
    project_paths = (str(pth) for pth in Path('projects/').glob('**/*.yaml') if pth not in path_blacklist
                     if 'dev' not in str(pth))

    return project_paths


@pytest.mark.parametrize('project_name', generateProjectPaths())
def test_lazyGenerateGraphs(project_name):

    pc = ProgramContext(config_path=get_os_config())

    recipes = load_recipes(project_name, pc.graph_config, project_folder='')

    if project_name.endswith('.yaml'):
        project_name = project_name[:-5]

    try:
        equations_solver(pc, project_name, recipes, pc.graph_config)
        assert True == True
    except Exception as e:
        assert True == False, f'Failed on {project_name} with error {e}'

@pytest.mark.parametrize('project_name', generateProjectPaths())
def test_flow(project_name):
    project_name = str(Path(project_name).relative_to('projects/'))

    pc = ProgramContext(config_path=get_os_config())

    try:
        flow(project_name, create_dirs=True, config_path=get_os_config())
        assert True == True
    except Exception as e:
        assert True == False, f'Failed on {project_name} with error {e}'

if __name__ == '__main__':
    for p in generateProjectPaths():
        print(p)