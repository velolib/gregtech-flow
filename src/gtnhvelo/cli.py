# Standard libraries
import logging
import os
import sys
import argparse
from pathlib import Path
from typing import Optional
import pkgutil

# Pypi libraries
import yaml
from rich import print as rprint
from rich.logging import RichHandler
from rich.panel import Panel
from rich.console import group
from rich.text import Text
import typer

# Internal libraries
from gtnhvelo.prototypes.linearSolver import systemOfEquationsSolverGraphGen
from gtnhvelo.graph import Graph
from gtnhvelo.data.loadMachines import recipesFromConfig

# Conditional imports based on OS
try:  # Linux
    import readline
except Exception:  # Windows
    import pyreadline3 as readline


class ProgramContext:

    def __init__(self, output_path: Path | str = 'output/', projects_path: Path | str = 'projects/', create_dirs: bool = True) -> None:
        """Program context class for gtnh-velo

        Args:
            output_path (Path | str, optional): Output path. Defaults to 'output'.
            projects_path (Path | str, optional): Projects path from which to search from. Defaults to 'projects'.
            create_dirs (bool, optional): Whether or not to create the directories specified. Defaults to True.
        """
        config = Path(os.getcwd(), 'config_factory_graph.yaml')
        template = pkgutil.get_data('gtnhvelo', 'resources/config_template.yaml')

        if not config.exists():
            self.cLog(f'Configuration file not found, generating new one at {Path(os.getcwd(), "config_factory_graph.yaml")}', logging.INFO)
            with open(config, mode='wb') as cfg:
                cfg.write(template)

        with config.open() as cfg:
            load = yaml.safe_load(cfg)
            if not load['CONFIG_VER'] == yaml.safe_load(template)['CONFIG_VER']:
                raise RuntimeError(f'Config version mismatch!')


        self.quiet = False

        # Load the data
        self.data = yaml.safe_load(pkgutil.get_data('gtnhvelo', 'resources/data.yaml'))

        # Logger setup
        if self.graph_config['DEBUG_LOGGING']:
            LOG_LEVEL = logging.DEBUG
        else:
            LOG_LEVEL = logging.INFO

        logging.basicConfig(handlers=[RichHandler(level=LOG_LEVEL, markup=True)], format='%(message)s', datefmt='[%X]', level='NOTSET')
        self.logger = logging.getLogger('rich')

        # Other stuff
        output_path = Path(output_path)
        if not output_path.exists() and create_dirs:
            output_path.mkdir()
        self.output_path = output_path

        projects_path = Path(projects_path)
        if not projects_path.exists() and create_dirs:
            projects_path.mkdir()
        self.projects_path = projects_path

    @property
    def graph_config(self):
        with open('config_factory_graph.yaml', 'r') as f:
            graph_config = yaml.safe_load(f)

        # Checks for graph_config
        if not graph_config['GRAPHVIZ']:
            raise RuntimeError('Graphviz option not inputted!')
        if graph_config['GRAPHVIZ'] == 'path':
            pass
        else:
            if Path(graph_config['GRAPHVIZ']).exists():
                os.environ["PATH"] += os.pathsep + str(Path(graph_config['GRAPHVIZ']))
            else:
                raise RuntimeError('Graphviz path does not exist')
        return graph_config

    def cLog(self, msg, level=logging.DEBUG):
        """Logging for gtnhvelo

        Args:
            msg (str): The message
            level (logging.DEBUG, logging.INFO, etc., optional): Logging level. Defaults to logging.DEBUG.
        """
        log = self.logger
        if level == logging.DEBUG:
            log.debug(f'{msg}')
        elif level == logging.INFO:
            log.info(f'{msg}')
        elif level == logging.WARNING:
            log.warning(f'{msg}')

    # @staticmethod
    # def standardGraphGen(self, project_name, recipes, graph_config, title=None):
    #     # Create graph and render, this is unused
    #     g = Graph(project_name, recipes, self, graph_config=graph_config, title=title)
    #     g.connectGraph()
    #     g.balanceGraph()
    #     g.outputGraphviz()

    def create_graph(self, project_name: Path | str) -> bool:
        """Centralized graph creation function to check if the project exists or not

        Args:
            project_name (Path | str): The project's path

        Returns:
            bool: Whether or not the project exists
        """
        project_name = str(project_name)
        if not project_name.endswith('.yaml'):
            # Assume when the user wrote "power/fish/methane", they meant "power/fish/methane.yaml"
            # This happens because autocomplete will not add .yaml if there are alternatives (like "power/fish/methane_no_biogas")
            project_name += '.yaml'

        project_relpath = self.projects_path / f'{project_name}'

        if project_relpath.exists():
            title = None
            with project_relpath.open(mode='r') as f:
                doc_load = list(yaml.safe_load_all(f))
                if len(doc_load) >= 2:
                    metadata = doc_load[0]
                    title = metadata['title']

            recipes = recipesFromConfig(project_name, self.graph_config, self.projects_path)

            if project_name.endswith('.yaml'):
                project_name = project_name[:-5]

            systemOfEquationsSolverGraphGen(self, project_name, recipes, self.graph_config, title)
            return True
        else:
            return False

    def interactive_cli(self) -> bool:
        """The interactive CLI for gtnhvelo

        Returns:
            bool: Whether or not the project file was found
        """
        readline.parse_and_bind('tab: complete')
        readline.set_completer_delims('')

        def filepath_completer(text, state):
            prefix = ''
            suffix = text
            if '/' in text:
                parts = text.split('/')
                prefix = '/'.join(parts[:-1])
                suffix = parts[-1]

            target_path = self.projects_path / prefix
            valid_tabcompletes = os.listdir(target_path)
            valid_completions = [x for x in valid_tabcompletes if x.startswith(suffix)]
            if state < len(valid_completions):  # Only 1 match
                completion = valid_completions[state]
                if prefix != '':
                    completion = ''.join([prefix, '/', completion])
                if not completion.endswith('.yaml'):
                    completion += '/'
                return completion
            else:
                return None

        @group()
        def get_elements():
            line_1 = Text()
            line_1.append('Please enter project path (example: "power/oil/light_fuel.yaml", tab autocomplete allowed)', style='bright_green')

            line_2 = Text()
            line_2.append('Type ', style='bright_white')
            line_2.append('\'end\' ', style='bright_green')
            line_2.append('to stop this session', style='bright_white')

            yield line_1
            yield line_2

        while True:
            readline.set_completer(filepath_completer)
            rprint(Panel(get_elements(), expand=False))
            rprint('[bright_white]> ', end='')
            the_input = str(input())

            match the_input:
                case 'end':
                    exit()
                case _:
                    return self.create_graph(the_input)

    def direct_cli(self, path: Path) -> bool:
        """Direct CLI implementation for gtnhvelo

        Args:
            path (Path): The path inputted from the command line

        Returns:
            bool: Whether or not a project was found at the inputted path
        """
        return self.create_graph(str(path))

    def run(self) -> None:
        """Runs the program
        """
        def run_typer(path: Optional[Path] = typer.Argument(None), quiet: bool = typer.Option(False, '--quiet', '-q')):
            if quiet:
                logger = self.logger
                logger.setLevel(logging.CRITICAL + 1)
            else:
                rprint(Panel('[bright_blue]gtnh-velo', expand=False))
            self.quiet = quiet

            while True:
                if path is None:
                    result = self.interactive_cli()
                    if not result:
                        rprint(Panel('[bright_white]Project could not be found!', expand=False, title='[bright_red]Error', style='bright_red'))
                else:
                    result = self.direct_cli(path)
                    if not result:
                        rprint(Panel('[bright_white]Project could not be found!', expand=False, title='[bright_red]Error', style='bright_red'))
                    exit()

        typer.run(run_typer)


def main():
    cli = ProgramContext()
    cli.run()


if __name__ == '__main__':
    main()
