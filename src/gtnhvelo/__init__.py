import os
from pathlib import Path
from gtnhvelo.module.flow import flow
import pkgutil

# TODO: Store config somewhere else
config = Path(os.getcwd(), 'flow_config.yaml')
if not config.exists():
    template = pkgutil.get_data('gtnhvelo', 'resources/config_template.yaml')
    assert template is not None
    with open(config, mode='wb') as cfg:
        cfg.write(template)
