from gtnhvelo import flow
from pathlib import Path
import pytest

def test_flow():
    paths = Path('tests/test_output').iterdir()
    [path.unlink() for path in paths if path.is_file()]

    flow('loopGraph.yaml', 'tests/test_output', 'tests/testProjects')

    found = False
    valid_exts = ['.svg', '.png', '.pdf']
    for ext in valid_exts:
        found = True if Path(f'tests/test_output/loopGraph{ext}').exists() else found
    assert found == True