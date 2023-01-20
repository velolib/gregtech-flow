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
from gregtech.flow.graph._solver import systemOfEquationsSolverGraphGen
from gregtech.flow.data.loadMachines import recipesFromConfig
from gregtech.flow.config.config_schema import config_schema

install(show_locals=True)


class ProgramContext:

    def __init__(self, output_path: Path | str = 'output/', projects_path: Path | str = 'projects/', create_dirs: bool = True, config_path: Path | str = Path('flow_config.yaml')) -> None:
        """Program context class for GT: Flow

        Args:
            output_path (Path | str, optional): Output path. Defaults to 'output'.
            projects_path (Path | str, optional): Projects path from which to search from. Defaults to 'projects'.
            create_dirs (bool, optional): Whether or not to create the directories specified. Defaults to True.
            config_path (Path | str, optional): Configuration file location. Will create one if nonexistent
        """
        self.config_cache: dict = {}
        self.project_cache: str = ''
        self.config_path = Path(config_path)
        self.quiet = False

        config = self.config_path
        template = pkgutil.get_data('gregtech.flow', 'resources/config_template.yaml')
        assert template is not None, 'Data file "resources/config_template.yaml" nonexistent, try reinstalling!'

        # Create config if not already created
        if not config.exists():
            with open(config, mode='wb') as cfg:
                cfg.write(template)

        # Check CONFIG_VER key
        with config.open() as cfg:
            load = yaml.safe_load(cfg)
            if not load['CONFIG_VER'] == yaml.safe_load(template)['CONFIG_VER']:
                raise RuntimeError(
                    f'Config version mismatch! Delete the old configuration file to regenerate')

        # Setup logger
        if self.graph_config['DEBUG_LOGGING']:
            LOG_LEVEL = logging.DEBUG
        else:
            LOG_LEVEL = logging.INFO
        logging.basicConfig(handlers=[RichHandler(
            level=LOG_LEVEL, markup=True)], format='%(message)s', datefmt='[%X]', level='NOTSET')
        self.logger = logging.getLogger('rich')

        # Load the game data
        data_yaml = pkgutil.get_data('gregtech.flow', 'resources/data.yaml')
        assert data_yaml is not None, 'Data file "resources/data.yaml" nonexistent, try reinstalling!'
        self.data = yaml.safe_load(data_yaml)

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
        with open('flow_config.yaml' if not self.config_path else self.config_path, 'r') as f:
            graph_config = yaml.safe_load(f)

            # Check for inequality between cache and loaded config
            # Used to skip expensive config schema validation
            if len(graph_config.keys()) != len(self.config_cache.keys()):  # trivial check
                config_schema.validate(graph_config)
                self.config_cache = graph_config
            elif graph_config != config_schema:  # order does not matter, only k:v pairs
                config_schema.validate(graph_config)
                self.config_cache = graph_config

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
        """Logging for gregtech.flow

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
                    header = doc_load[0]
                    title = header['title']
                    self.cLog(f'Current project: "{title}" by [bright_green]{header["creator"]}', logging.INFO)
                else:
                    self.cLog(f'Current project: "{project_name}"', logging.INFO)

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
        """The interactive CLI for gregtech.flow

        Returns:
            bool: Whether or not the project file was found
        """

        header = Layout(Panel(Align('[bold bright_cyan]GT: Flow', align='center',
                        vertical='middle'), border_style='bold bright_cyan'), name='header', size=3)

        guide_text = textwrap.dedent('''\
        [bright_green]Please enter project path (example: "[underline]power/oil/light_fuel.yaml[/]")[/]
        [bright_green]Tab completion is [underline]enabled[/][/]
        [bright_white]Valid commands:[/]
        [bright_white]- [/][bright_green]end[/][bright_white] / [/][bright_green]stop[/][bright_white] / [/][bright_green]exit[/][bright_white]: Stop the program[/]
        [bright_white]- [/][bright_green]all[/][bright_white]: Select all files for graph creation[/]
        [bright_white]- [/][bright_green]last[/][bright_white]: The last project inputted[/]
        ''')
        guide = Layout(Panel(guide_text, border_style='bold bright_magenta',
                       title='guide.txt', title_align='left'), name='guide')

        links_text = textwrap.dedent('''\
        [bright_green link=https://github.com/velolib/gregtech-flow]GitHub Repository[/][bright_white]: [/][underline bright_cyan link=https://github.com/velolib/gregtech-flow]https://github.com/velolib/gregtech-flow[/]
        [bright_green link=https://github.com/velolib/gregtech-flow/wiki]Wiki[/][bright_white]: [/][underline bright_cyan link=https://github.com/velolib/gregtech-flow/wiki]https://github.com/velolib/gregtech-flow/wiki[/]
        ''')
        links = Layout(Panel(links_text, border_style='bold bright_white',
                       title='links.txt', title_align='left'), name='links')

        errors = Layout(Panel('[bright_white]No errors found.' if not current_error else '[bright_red]' +
                        current_error, border_style='bold bright_yellow', title='errors.log', title_align='left'), name='errors')

        root_layout = Layout()
        root_layout.size = 4
        root_layout.split_column(header, Layout(name='content', size=8))
        root_layout['content'].split_row(guide, Layout(name='right_sect'))

        # TODO: Increase functionality of the errors panel
        root_layout['content']['right_sect'].split_column(links, errors)

        console = Console(height=11)

        prompt_style = Style.from_dict({'bigger_than': '#ffffff'})
        prompt_message = [('class:bigger_than', '> ')]

        while True:
            console.print(root_layout)
            console.print('[bright_white]> ', end='')

            projects = list(map(lambda p: str(p.relative_to(self.projects_path)), self.projects_path.glob('**/*.yaml')))
            path_completer = WordCompleter(projects)

            sel_option = prompt(prompt_message, completer=path_completer, style=prompt_style)  # type: ignore
            match sel_option:
                case 'end' | 'stop' | 'exit':
                    exit()
                case 'all':
                    console.print('')
                    console.print(Rule(style='bright_white',
                                  title='[bold bright_white]latest.log', align='center'))

                    valid_paths = [self.create_graph(v.relative_to(self.projects_path)) for v in Path(
                        self.projects_path).glob('**/*.yaml') if 'dev' not in str(v)]

                    console.print(Rule(style='bright_white'))
                    console.print('')
                    return all(valid_paths)
                case 'last' | '':
                    console.print('')
                    console.print(Rule(style='bright_white',
                                  title='[bold bright_white]latest.log', align='center'))
                    create_graph = self.create_graph(self.project_cache)
                    if not create_graph:
                        print('')
                    console.print(Rule(style='bright_white'))
                    console.print('')
                    return create_graph
                case _:
                    console.print('')
                    console.print(Rule(style='bright_white',
                                  title='[bold bright_white]latest.log', align='center'))
                    create_graph = self.create_graph(sel_option)
                    if not create_graph:
                        print('')
                    console.print(Rule(style='bright_white'))
                    console.print('')
                    self.project_cache = sel_option
                    return create_graph

    def direct_cli(self, path: Path) -> bool:
        """Direct CLI implementation for gregtech.flow

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
                        rprint(Panel(Align('[bold bright_cyan]GT: Flow', align='center',
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
