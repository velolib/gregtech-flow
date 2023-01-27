# Script to generate all projects in the repository.
# Used for the website
from gregtech.flow import flow
from pathlib import Path
import typer

def main(assets_path_absolute: Path):

    [
        flow(project.relative_to('projects'),
             create_dirs=True,
             config_path=Path('scripts/script_config.yaml'),
             output_path=assets_path_absolute)
        for project in Path('projects/').glob('**/*.yaml') if 'dev' not in str(project)
    ]

if __name__ == '__main__':
    typer.run(main)