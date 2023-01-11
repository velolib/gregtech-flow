from gtnhvelo.cli import ProgramContext
from pathlib import Path
import logging


def flow(project_name: Path | str, output_path: Path | str = 'output/', projects_path: Path | str = 'projects/', config_path: Path | str = 'config_factory_graph.yaml'):
    """
    gtnh-velo flow wrapper

    Args:
        project_name (Path | str): Project path relative to projects_path
        output_path (Path | str, optional): Output path. Defaults to 'output/'.
        projects_path (Path | str, optional): Path to projects directory. Defaults to 'projects/'.
        config_path (Path | str): Configuration file path. Will create one if nonexistent. Defaults to 'config_factory_graph.yaml'
    """

    project_name = Path(project_name)
    projects_path = Path(projects_path)
    output_path = Path(output_path)
    config_path = Path(config_path)

    pc = ProgramContext(output_path, projects_path, False, config_path)

    if not output_path.exists() or not output_path.is_dir():
        raise RuntimeError(f'Invalid output_path: {output_path}')
    if not projects_path.exists() or not projects_path.is_dir():
        raise RuntimeError(f'Invalid projects_path: {projects_path}')

    rich = logging.getLogger('rich')
    rich.setLevel(logging.CRITICAL + 1)
    pc.quiet = True
    if not pc.create_graph(project_name):
        raise RuntimeError(f'Invalid project_name: {project_name}')
