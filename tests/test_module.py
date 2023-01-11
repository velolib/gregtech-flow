from gtnhvelo import flow
from pathlib import Path
import pytest
import os

def test_flow():
    """
    Run locally
    """
    path_vars = (os.environ.get('path')).split(os.pathsep)
    if not [x for x in path_vars if 'Graphviz' in x if 'bin' in x]:
        pytest.skip()

    paths = Path('output/').iterdir()
    [path.unlink() for path in paths if path.is_file()]

    flow('loopGraph.yaml', 'output/', 'tests/testProjects', 'tests/test_config.yaml')

    found = False
    valid_exts = ['.svg', '.png', '.pdf']
    for ext in valid_exts:
        found = True if Path(f'output/loopGraph{ext}').exists() else found
    assert found == True