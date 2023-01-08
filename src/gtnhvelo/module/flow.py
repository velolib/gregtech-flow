from gtnhvelo.cli import ProgramContext
from pathlib import Path
import logging


def flow(project_name: Path | str, output_path: Path | str = 'output/', projects_path: Path | str = 'projects/'):
    """Command line wrapper for gtnh-velo

    Args:
        project_name (Path | str): Project path relative to /projects
    """

    project_name = Path(project_name)
    projects_path = Path(projects_path)
    output_path = Path(output_path)

    pc = ProgramContext(output_path, projects_path, False)

    if not output_path.exists() or not output_path.is_dir():
        raise RuntimeError(f'Invalid output_path: {output_path}')
    if not projects_path.exists() or not projects_path.is_dir():
        raise RuntimeError(f'Invalid projects_path: {projects_path}')

    rich = logging.getLogger('rich')
    rich.setLevel(logging.CRITICAL + 1)
    pc.quiet = True
    if not pc.create_graph(project_name):
        raise RuntimeError(f'Invalid project_name: {project_name}')
