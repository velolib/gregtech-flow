# Tests for _utils.py that are probably not needed
from gtnhvelo.graph._utils import swapIO, userRound
import yaml
import sys
from functools import lru_cache

import pytest

from gtnhvelo.data.loadMachines import recipesFromConfig

@lru_cache(1)
def get_os_config():
    match sys.platform:
        case 'linux':
            return 'tests/test_config_linux.yaml'
        case 'win32':
            return 'tests/test_config_windows.yaml'
        case _:
            raise NotImplementedError(f'Invalid OS for testing: "{sys.platform}", contact dev for implementation!')

def loadTestConfig():
    with open(get_os_config(), 'r') as f:
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