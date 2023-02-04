"""CLI and Program Context module for GT: Flow.

This module is used to provide the program context for other modules.
It is also used to run the Interactive CLI and the Direct CLI.
"""
import logging
import os
import pkgutil
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Optional

import typer
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from rich import print as rprint
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.logging import RichHandler
from rich.panel import Panel
from rich.rule import Rule
from rich.traceback import install

from gregtech.flow.graph._solver import equations_solver
from gregtech.flow.recipe.load_project import load_recipes
from gregtech.flow.schemas import validate_config, yaml

install(show_locals=True)


class ProgramContext:
    """Class to provide context for other functions. Also used for the GT: Flow CLI."""

    def __init__(self,
                 output_path: Path | str = 'output/',
                 projects_path: Path | str = 'projects/',
                 create_dirs: bool = True,
                 config_path: Path | str = Path('flow_config.yaml')) -> None:
        """Initializes ProgramContext and also sets up GT: Flow for use.

        Args:
            output_path (Path | str, optional): Output path. Defaults to 'output'.
            projects_path (Path | str, optional): Projects path from which to search from. Defaults to 'projects'.
            create_dirs (bool, optional): Whether or not to create the directories specified. Defaults to True.
            config_path (Path | str, optional): Configuration file location. Will create one if nonexistent
        """
        self.config_cache: dict = {}
        self.project_cache: str = ''
        self.config_path = Path(config_path) if config_path else Path('flow_config.yaml')
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
            load = yaml.load(cfg)
            template_load = yaml.load(template)['CONFIG_VER']
            if not load['CONFIG_VER'] == template_load:
                raise RuntimeError(
                    f'Config version mismatch! Delete the old configuration file to regenerate {load["CONFIG_VER"]} {template_load}')

        # Setup logger
        if self.graph_config['DEBUG_LOGGING']:
            log_level = logging.DEBUG
        else:
            log_level = logging.INFO
        logging.basicConfig(handlers=[RichHandler(
            level=log_level, markup=True)], format='%(message)s', datefmt='[%X]', level='NOTSET')
        self.logger = logging.getLogger('rich')

        # Load the game data
        data_yaml = pkgutil.get_data('gregtech.flow', 'resources/data.yaml')
        assert data_yaml is not None, 'Data file "resources/data.yaml" nonexistent, try reinstalling!'
        self.data = yaml.load(data_yaml)

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
    def graph_config(self) -> dict:
        """Graph configuration.

        Returns:
            dict: Graph configuration
        """
        with self.config_path.open(mode='r') as f:
            graph_config = yaml.load(f)

            # Check for inequality between cache and loaded config
            # Used to skip expensive config schema validation
            # trivial check + equality check
            if (len(graph_config.keys()) != len(self.config_cache.keys())) or (graph_config != self.config_cache):
                validate_config(graph_config)
                self.config_cache = graph_config

        # Checks for graph_config
        if graph_config['GRAPHVIZ'] == 'path':
            pass
        else:
            if Path(graph_config['GRAPHVIZ']).exists():
                os.environ["PATH"] += os.pathsep + str(Path(graph_config['GRAPHVIZ']))
            else:
                raise RuntimeError('Graphviz path does not exist')
        return graph_config

    def log(self, msg, level=logging.DEBUG):
        """Logging method for gregtech.flow.

        Args:
            msg (str): The message
            level (logging.DEBUG, logging.INFO, etc., optional): Logging level. Defaults to logging.DEBUG.
        """
        log = self.logger
        log.log(level, f'{msg}')

    def create_graph(self, project_name: Path | str) -> bool:
        """Centralized graph creation function to check if the project exists or not.

        Args:
            project_name (Path | str): The project's path

        Returns:
            bool: Whether or not the project exists
        """
        project_name = str(project_name)
        if not project_name.endswith('.yaml'):
            project_name += '.yaml'

        project_relpath = self.projects_path / f'{project_name}'

        if project_relpath.exists():
            title = ''
            with project_relpath.open(mode='r') as f:
                doc_load = list(yaml.load_all(f))
                if len(doc_load) >= 2:
                    header = doc_load[0]
                    title = header['title']
                    self.log(
                        f'Current project: "{title}" by [bright_green]{header["creator"]}', logging.INFO)
                else:
                    self.log(f'Current project: "{project_name}"', logging.INFO)

            recipes = load_recipes(
                project_name, self.graph_config, self.projects_path)

            if project_name.endswith('.yaml'):
                project_name = project_name[:-5]

            equations_solver(
                self, project_name, recipes, title)
            return True
        else:
            return False

    def create_filetree(self, path: Path, pfx: str = '', max_depth: int = 720, emoji: bool = True) -> Iterator[str] | list:
        """Creates a file tree of the input path.

        Args:
            path (Path): Path of the directory
            pfx (str, optional): Prefix. Defaults to ''.
            max_depth (int, optional): Recursion limit of the function. Defaults to 720 (arbitrary).
            emoji (bool, optional): Whether or not to use emojis. Defaults to True.

        Yields:
            Generator[str, None, None]: Lines of the file tree in string form.
        """
        if max_depth > 0:
            space = '    '
            branch = '│   '
            tee = '├── '
            last = '└── '

            contents = list(path.iterdir())
            pointers = [tee] * (len(contents) - 1) + [last]
            for pointer, path in zip(pointers, contents):
                if emoji:
                    if path.is_file():
                        yield pfx + pointer + ':page_facing_up: ' + path.name
                    else:
                        yield pfx + pointer + ':file_folder: ' + path.name
                else:
                    yield pfx + pointer + path.name
                if path.is_dir():
                    extension = branch if pointer == tee else space
                    yield from self.create_filetree(path, f'{pfx}{extension}')
        else:
            return ['Exceeded maximum recursion limit',]

    def interactive_cli(self, current_error) -> bool:
        """The interactive CLI for gregtech.flow.

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
        [bright_white]- [/][bright_green]last[/][bright_white]: The last project inputted (or just type nothing)[/]
        [bright_white]- [/][bright_green]tree[/][bright_white]: Prints the './projects/' file tree[/]
        ''')
        guide = Layout(Panel(guide_text, border_style='bold bright_magenta',
                       title='guide.txt', title_align='left'), name='guide')

        links_text = textwrap.dedent('''\
        [bright_green link=https://github.com/velolib/gregtech-flow]GitHub Repository[/][bright_white]: [/][underline bright_cyan link=https://github.com/velolib/gregtech-flow]https://github.com/velolib/gregtech-flow[/]
        [bright_green link=https://github.com/velolib/gregtech-flow/wiki]Website[/][bright_white]: [/][underline bright_cyan link=https://velolib.github.io/gregtech-flow/]https://velolib.github.io/gregtech-flow/[/]
        ''')
        links = Layout(Panel(links_text, border_style='bold bright_white',
                       title='links.txt', title_align='left'), name='links')

        errors = Layout(Panel('[bright_white]No errors found.' if not current_error else '[bright_red]' +
                        current_error, border_style='bold bright_yellow', title='errors.log', title_align='left'), name='errors')

        root_layout = Layout()
        root_layout.size = 4
        root_layout.split_column(header, Layout(name='content', size=9))
        root_layout['content'].split_row(guide, Layout(name='right_sect'))

        # TODO: Increase functionality of the errors panel
        root_layout['content']['right_sect'].split_column(links, errors)

        console = Console(height=12)

        prompt_style = Style.from_dict({'bigger_than': '#ffffff'})
        prompt_message = [('class:bigger_than', '> ')]

        while True:
            console.print(root_layout)
            console.print('[bright_white]> ', end='')

            projects = list(map(lambda p: str(p.relative_to(self.projects_path)),
                            self.projects_path.glob('**/*.yaml')))
            path_completer = WordCompleter(projects)

            sel_option = prompt(prompt_message, completer=path_completer,  # type: ignore
                                style=prompt_style)  # type: ignore
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
                case 'tree':
                    console.print('')
                    console.print(Rule(style='bright_white',
                                  title='[bold bright_white]tree.txt', align='center'))
                    for x in self.create_filetree(Path(self.projects_path)):
                        console.print(x)
                    console.print(Rule(style='bright_white'))
                    prompt('')
                    return True
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
        """Direct CLI implementation for gregtech.flow.

        Args:
            path (Path): The path inputted from the command line

        Returns:
            bool: Whether or not a project was found at the inputted path
        """
        return self.create_graph(str(path))

    def run(self) -> None:
        """Runs the CLI."""
        def run_typer(path: Optional[Path] = typer.Argument(None), quiet: bool = typer.Option(False, '--quiet', '-q')):
            if quiet:
                logger = self.logger
                logger.setLevel(logging.CRITICAL + 1)
            self.quiet = quiet

            icli_error = None
            while True:
                if path is None:
                    cols, _ = os.get_terminal_size()
                    if cols <= 139:
                        raise NotImplementedError(
                            'Terminal width <= 139 columns is not supported. Use the direct CLI instead.')
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


def run_cli():
    """Runs the CLI."""
    cli = ProgramContext()
    cli.run()


if __name__ == '__main__':
    run_cli()
