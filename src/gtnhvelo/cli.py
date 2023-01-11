# Standard libraries
import logging
import os
from pathlib import Path
from typing import Optional
import pkgutil
import textwrap

# Pypi libraries
import yaml
from rich import print as rprint
from rich.logging import RichHandler
from rich.panel import Panel
from rich.console import Console
from rich.traceback import install
from rich.layout import Layout
from rich.align import Align
from rich.rule import Rule
import typer
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style

# Internal libraries
from gtnhvelo.graph._solver import systemOfEquationsSolverGraphGen
from gtnhvelo.data.loadMachines import recipesFromConfig

install(show_locals=True)


class ProgramContext:

    def __init__(self, output_path: Path | str = 'output/', projects_path: Path | str = 'projects/', create_dirs: bool = True, config_path=None) -> None:
        """Program context class for gtnh-velo

        Args:
            output_path (Path | str, optional): Output path. Defaults to 'output'.
            projects_path (Path | str, optional): Projects path from which to search from. Defaults to 'projects'.
            create_dirs (bool, optional): Whether or not to create the directories specified. Defaults to True.
        """
        self.config_path = config_path
        self.quiet = False

        # TODO: Stop using an actual file in the cwd for the config
        # Get config and config template
        config = Path('config_factory_graph.yaml')
        template = pkgutil.get_data('gtnhvelo', 'resources/config_template.yaml')
        assert template is not None

        # Create config if not already created
        if not config.exists():
            self.cLog(
                f'Configuration file not found, generating new one at {Path(os.getcwd(), "config_factory_graph.yaml")}', logging.INFO)
            with open(config, mode='wb') as cfg:
                cfg.write(template)

        # Check CONFIG_VER key
        with config.open() as cfg:
            load = yaml.safe_load(cfg)
            if not load['CONFIG_VER'] == yaml.safe_load(template)['CONFIG_VER']:
                raise RuntimeError(
                    f'Config version mismatch! Delete the old configuration file to regenerate')

        # Load the game data
        data_yaml = pkgutil.get_data('gtnhvelo', 'resources/data.yaml')
        assert data_yaml is not None
        self.data = yaml.safe_load(data_yaml)

        # Setup logger
        if self.graph_config['DEBUG_LOGGING']:
            LOG_LEVEL = logging.DEBUG
        else:
            LOG_LEVEL = logging.INFO
        logging.basicConfig(handlers=[RichHandler(
            level=LOG_LEVEL, markup=True)], format='%(message)s', datefmt='[%X]', level='NOTSET')
        self.logger = logging.getLogger('rich')

        # Create paths if selected option
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
        with open('config_factory_graph.yaml' if not self.config_path else self.config_path, 'r') as f:
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

            recipes = recipesFromConfig(
                project_name, self.graph_config, self.projects_path)

            if project_name.endswith('.yaml'):
                project_name = project_name[:-5]

            systemOfEquationsSolverGraphGen(
                self, project_name, recipes, self.graph_config, title)
            return True
        else:
            return False

    def interactive_cli(self, current_error) -> bool:
        """The interactive CLI for gtnhvelo

        Returns:
            bool: Whether or not the project file was found
        """

        # TODO: Clean this up
        guide_text = textwrap.dedent('''\
        [bright_green]Please enter project path (example: "[underline]power/oil/light_fuel.yaml[/]")[/]
        [bright_green]Tab completion is [underline]enabled[/][/]
        [bright_white]Valid commands:[/]
        [bright_white]- [/][bright_green]end[/][bright_white] / [/][bright_green]stop[/][bright_white] / [/][bright_green]exit[/][bright_white]: Stop the program[/]
        ''')

        links_text = textwrap.dedent('''\
        [bright_green link=https://github.com/velolib/gtnh-velo]GitHub Repository[/][bright_white]: [/][underline bright_cyan link=https://github.com/velolib/gtnh-velo]https://github.com/velolib/gtnh-velo[/]
        [bright_green link=https://github.com/velolib/gtnh-velo/wiki]Wiki[/][bright_white]: [/][underline bright_cyan link=https://github.com/velolib/gtnh-velo/wiki]https://github.com/velolib/gtnh-velo/wiki[/]
        ''')

        # TODO: Add more commands
        main_ly = Layout()
        main_ly.size = 4
        main_ly.split_column(Layout(Panel(Align('[bold bright_cyan]gtnh-velo', align='center', vertical='middle'),
                             border_style='bold bright_cyan'), name='header', size=3), Layout(name='content', size=8))
        main_ly['content'].split_row(
            Layout(Panel(guide_text, border_style='bold bright_magenta',
                   title='guide.txt', title_align='left'), name='left'),
            Layout(name='right')
        )

        # TODO: Increase functionality of the errors panel
        main_ly['content']['right'].split_column(
            Layout(Panel(links_text, border_style='bold bright_white',
                   title='links.txt', title_align='left'), name='credits'),
            Layout(Panel('[bright_white]No errors found.' if not current_error else '[bright_red]' + current_error,
                   border_style='bold bright_yellow', title='errors.log', title_align='left'), name='errors')
        )

        console = Console(height=11)

        prompt_style = Style.from_dict({'bigger_than': '#ffffff'})
        prompt_message = [('class:bigger_than', '> ')]

        while True:
            console.print(main_ly)
            console.print('[bright_white]> ', end='')

            projects = list(map(lambda p: str(p.relative_to(self.projects_path)), self.projects_path.glob('**/*.yaml')))
            path_completer = WordCompleter(projects)

            selected_path = prompt(prompt_message, completer=path_completer, style=prompt_style)  # type: ignore

            match selected_path:
                case 'end' | 'stop' | 'exit':
                    exit()
                case _:
                    console.print('')
                    console.print(Rule(style='bright_white',
                                  title='[bold bright_white]latest.log', align='center'))
                    create_graph = self.create_graph(selected_path)
                    if not create_graph:
                        print('')
                    console.print(Rule(style='bright_white'))
                    console.print('')
                    return create_graph

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
            self.quiet = quiet

            icli_error = None
            while True:
                if path is None:
                    result = self.interactive_cli(icli_error)
                    icli_error = None
                    if not result:
                        icli_error = 'Project could not be found!'
                else:
                    if not quiet:
                        rprint(Panel(Align('[bold bright_cyan]gtnh-velo', align='center',
                               vertical='middle'), border_style='bold bright_cyan'))
                    result = self.direct_cli(path)
                    if not result:
                        rprint(Panel('[bright_white]Project could not be found!',
                               expand=False, title='[bright_red]Error', style='bright_red'))
                    exit()

        typer.run(run_typer)


def main():
    cli = ProgramContext()
    cli.run()


if __name__ == '__main__':
    main()
