# This file is used to regenerate the samples used in the README.md

import subprocess
import sys
import shutil
import time
from pathlib import Path

sample_dir = Path('samples/')

if sample_dir.exists():
    shutil.rmtree(sample_dir)
time.sleep(0.01)
sample_dir.mkdir()

sample_paths = [
    Path('plastics/epoxid'),
    Path('minerals/rutile-titanium'),
]

for project in sample_paths:
    with subprocess.Popen([sys.executable, 'factory_graph.py', str(project), 'png']):
        pass
    graph_path = Path('output/') / f'{project}.png'
    shutil.copy(graph_path, sample_dir)