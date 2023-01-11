from gtnhvelo import flow
from pathlib import Path
import pytest

def test_flow():
    paths = Path('output/').iterdir()
    [path.unlink() for path in paths if path.is_file()]

    flow('loopGraph.yaml', 'output/', 'tests/testProjects')

    found = False
    valid_exts = ['.svg', '.png', '.pdf']
    for ext in valid_exts:
        found = True if Path(f'output/loopGraph{ext}').exists() else found
    assert found == True