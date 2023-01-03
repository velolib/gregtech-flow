import os
from pathlib import Path
import pkgutil

# TODO: Store config somewhere else
config = Path(os.getcwd(), 'config_factory_graph.yaml')
if not config.exists():
    template = pkgutil.get_data('gtnhvelo', 'resources/config_template.yaml')

    with open(config, mode='wb') as cfg:
        cfg.write(template)
