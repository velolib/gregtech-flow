# flake8: noqa
# Script to generate all projects in the repository.
# Used for the website
from gregtech.flow.wrapper import flow
from pathlib import Path
import time
import shutil
import typer


def main(assets_path_absolute: Path):
    if not assets_path_absolute.exists():
        assets_path_absolute.mkdir()
    else:
        shutil.rmtree(str(assets_path_absolute))
        time.sleep(0.1)
        assets_path_absolute.mkdir()
    [
        flow(project.relative_to('projects'),
             create_dirs=True,
             config_path=Path('scripts/script_config.yaml'),
             output_path=assets_path_absolute)
        for project in Path('projects/').glob('**/*.yaml') if 'dev' not in str(project)
    ]
    [
        project.unlink() for project in (assets_path_absolute.glob('**/*')) if project.is_file() if project.suffix == ''
    ]


if __name__ == '__main__':
    typer.run(main)
