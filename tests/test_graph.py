# flake8: noqa
import sys
from pathlib import Path
from functools import lru_cache

import pytest
import random
import string

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

def get_fail(num):
    specified = [
        'κόσμε',
        '������',
        '����',
        '���',
        '﷔﷕﷖﷗﷘﷙﷚﷛﷜﷝﷞﷟﷠﷡﷢﷣﷤',
    ]
    runtime = [''.join(random.choices(string.ascii_uppercase + string.digits, k=5)) for _ in range(num-len(specified))]
    return specified + runtime

# ---------------------------------------------------------------------------- #
#                                     Tests                                    #
# ---------------------------------------------------------------------------- #

@pytest.mark.parametrize('project_name', get_projects())
def test_solver(project_name) -> None:
    """Used to test the GT: Flow equations solver directly.

    Args:
        project_name (str): Project name as a string
    """
    pc = ProgramContext(config_path=pytest.os_config)

    recipes = load_project(project_name, pc.graph_config, project_dir='')

    if project_name.endswith('.yaml'):
        project_name = project_name[:-5]

    try:
        equations_solver(pc, project_name, recipes)
        if not (Path(project_name).with_suffix('.yaml')).exists():
            assert True == False
        assert True == True
    except Exception as e:
        assert True == False, f'Failed on {project_name} with error {e}'

@pytest.mark.parametrize('project_name', get_projects(remove_project=True))
def test_flow(project_name: str) -> None:
    """Used to test the flow() CLI wrapper.

    Args:
        project_name (str): Project name as a string
    """
    project_name = str(Path(project_name))

    pc = ProgramContext(config_path=pytest.os_config)

    try:
        flow(project_name, create_dirs=True, config_path=pytest.os_config)
        if not (Path('projects') / Path(project_name).with_suffix('.yaml')).exists():
            assert True == False
        assert True == True
    except Exception as e:
        assert True == False, f'Failed on {project_name} with error {e}'

@pytest.mark.parametrize('project_name', get_projects(remove_project=True))
def test_dcli(project_name):
    """Used to test the GT: Flow Direct CLI.

    Args:
        project_name (str): Project name as a string
    """
    pc = ProgramContext(config_path=pytest.os_config)

    with pytest.raises(SystemExit):
        pc._run_typer(Path(project_name), True, False)
    
    if not (Path('projects') / Path(project_name).with_suffix('.yaml')).exists():
        assert True == False, f'Failed on {project_name}'

@pytest.mark.parametrize('s', get_fail(15))
def test_fail(s):
    """Used to test the GT: Flow CLI by failing.

    Args:
        project_name (str): Project name as a string
    """
    pc = ProgramContext(config_path=pytest.os_config)
    try:
        pc._run_typer(Path(s), True, False)
    except RuntimeError:
        assert True == True
    except SystemExit:
        assert True == False, f'Succeeded on {s}.'
    else:
        assert True == False, f'Succeeded on {s}.'
    