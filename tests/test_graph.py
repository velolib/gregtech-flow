# flake8: noqa
import sys
from pathlib import Path
from functools import lru_cache

import pytest
import subprocess

from gregtech.flow.recipe.load_project import load_project
from gregtech.flow.graph._solver import equations_solver
from gregtech.flow.cli import ProgramContext
from gregtech.flow import flow

# ---------------------------------------------------------------------------- #
#                               Preliminary setup                              #
# ---------------------------------------------------------------------------- #

match sys.platform:
    case 'linux':
        pytest.os_config = 'tests/test_config_linux.yaml'
        pytest.os_config_pathlib = Path('./tests/test_config_linux.yaml').resolve()
    case 'win32':
        pytest.os_config = 'tests/test_config_windows.yaml'
        pytest.os_config_pathlib = Path('./tests/test_config_windows.yaml').resolve()
    case _:
        raise NotImplementedError(f'Invalid OS for testing: "{sys.platform}", contact dev for implementation!')

def get_projects(ignore_broken: bool = True, remove_project: bool = False):
    if ignore_broken:
        path_blacklist = [
            Path('circuits/nanocircuits.yaml'),
        ]
    else:
        path_blacklist = []

    if remove_project:
        return (str(pth.relative_to('projects/')) for pth in Path('projects/').glob('**/*.yaml') if pth not in path_blacklist
                        if Path('projects/dev') not in list(pth.parents))
    else:
        return (str(pth) for pth in Path('projects/').glob('**/*.yaml') if pth not in path_blacklist
                        if Path('projects/dev') not in list(pth.parents))

# ---------------------------------------------------------------------------- #
#                                     Tests                                    #
# ---------------------------------------------------------------------------- #

@pytest.mark.parametrize('project_name', get_projects())
def test_solver(project_name) -> None:
    """Used to test the equations solver directly.

    Args:
        project_name (str): Project name as a string
    """
    pc = ProgramContext(config_path=pytest.os_config)

    recipes = load_project(project_name, pc.graph_config, project_dir='')

    if project_name.endswith('.yaml'):
        project_name = project_name[:-5]

    try:
        equations_solver(pc, project_name, recipes)
        assert True == True
    except Exception as e:
        assert True == False, f'Failed on {project_name} with error {e}'

@pytest.mark.parametrize('project_name', get_projects(remove_project=True))
def test_direct_cli(project_name: str) -> None:
    """Used to test the Direct CLI.

    Args:
        project_name (str): Project name as a string
    """
    # TODO: Improve this a lot
    with subprocess.Popen(['poetry', 'run', 'flow', project_name, '--config', f'{pytest.os_config_pathlib}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        out, err = process.communicate()
        if 'Project could not be found!' in str(out):
            assert True == False, f'Failed on {project_name}. The project could not be found!'
        if process.returncode != 0:
            print(f'{out=}')
            print(f'{err=}')
            assert True == False, f'Failed on {project_name}.'

@pytest.mark.parametrize('project_name', get_projects())
def test_flow(project_name: str) -> None:
    """Used to test the flow() CLI wrapper.

    Args:
        project_name (str): Project name as a string
    """
    project_name = str(Path(project_name).relative_to('projects/'))

    pc = ProgramContext(config_path=pytest.os_config)

    try:
        flow(project_name, create_dirs=True, config_path=pytest.os_config)
        assert True == True
    except Exception as e:
        assert True == False, f'Failed on {project_name} with error {e}'
