# This file is used to regenerate the samples used in the README.md

import subprocess
import sys
import shutil
import os
from pathlib import Path

sample_dir = Path('samples/')

if sample_dir.exists():
    shutil.rmtree(sample_dir)
sample_dir.mkdir()

sample_paths = [
    Path('plastics/epoxid'),
    Path('minerals/rutile-titanium'),
]

for project in sample_paths:
    with subprocess.Popen([sys.executable, 'factory_graph.py', str(project), 'png']):
        pass
    graph_path = Path('output/') / project
    graph_path.rename(sample_dir / f'{graph_path.stem}.png')