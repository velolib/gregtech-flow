"""CLI and Program Context module for GT: Flow.

This module is used to provide the program context for other modules.
It is also used to run the Interactive CLI and the Direct CLI.
"""
from __future__ import annotations

import contextlib
import inspect
import logging
import os
import pkgutil
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style
from rich import print as rprint
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.logging import RichHandler
from rich.panel import Panel
from rich.rule import Rule
from rich.traceback import install

from gregtech.flow.graph._solver import equations_solver
from gregtech.flow.recipe.load_project import load_project
from gregtech.flow.schemas import validate_config, validate_header, yaml

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from prompt_toolkit.document import Document

install(show_locals=True, max_frames=100)


class PathCompleter(Completer):
    """Completer class for the Interactive CLI.

    Includes support for backslashes and frontslashes.
    """

    def __init__(self, directory: Path) -> None:
        """Class constructor for PathCompleter.

        Args:
            directory (Path): Directory
        """
        assert directory.is_dir()
        self.directory = Path(directory)
        self.display_dict: dict = {}
        self.meta_dict: dict = {}

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """Get completions for prompt_toolkit."""
        if sys.platform == 'win32':
            if '\\' in document.text:
                backslash = True
            else:
                backslash = False
        else:
            backslash = False

        words = [(x.relative_to(self.directory).as_posix() if not backslash else str(x.relative_to(self.directory)))
                 for x in self.directory.glob('**/*.yaml')]
        if callable(words):
            words = words()

        # Get word/text before cursor.
        word_before_cursor = document.text_before_cursor
        word_before_cursor = word_before_cursor.lower()

        def word_matches(word: str) -> bool:
            """True when the word before the cursor matches."""
            word = word.lower()
            return word.startswith(word_before_cursor)

        for a in words:
            if word_matches(a):
                display = self.display_dict.get(a, a)
                display_meta = self.meta_dict.get(a, "")
                yield Completion(
                    text=a,
                    start_position=-len(word_before_cursor),
                    display=display,
                    display_meta=display_meta,
                )


class ProgramContext:
    """Class to provide context and data for other functions. Also used for the GT: Flow CLI."""

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
            config_path (Path | str, optional): Configuration file location. Will create one if nonexistent no matter what
        """
        # Misc
        self._project_cache: str = ''  # For 'last' in Interactive CLI
        self.quiet = False  # Default value
        self.running_from: Literal['WRAPPER', 'INTERACTIVE', 'DIRECT'] = 'WRAPPER'  # Default value

        # Load the config
        self.config_path = Path(config_path) if config_path else Path('flow_config.yaml')
        self.graph_config: dict = {}
        self._config_cache: dict = {}  # Used to skip schema validation
        self._config_template = pkgutil.get_data('gregtech.flow', 'resources/config_template.yaml')
        assert self._config_template is not None, 'Data file "resources/config_template.yaml" nonexistent, try reinstalling!'
        self.reload_graph_config()

        # Setup logger
        if self.graph_config['DEBUG_LOGGING']:
            log_level = logging.DEBUG
        else:
            log_level = logging.INFO
        logging.basicConfig(handlers=[RichHandler(level=log_level, markup=True)],
                            format='%(message)s',
                            datefmt='[%X]',
                            level='NOTSET')
        self.logger = logging.getLogger('rich')

        # Load the data required for running GT: Flow's calculations
        data_yaml = pkgutil.get_data('gregtech.flow', 'resources/data.yaml')
        assert data_yaml is not None, 'Data file "resources/data.yaml" nonexistent, try reinstalling!'
        self.data = yaml.load(data_yaml)

        # Create output and projects directory
        if create_dirs:
            output_path = Path(output_path)
            if not output_path.exists():
                output_path.mkdir()
            self.output_path = output_path

            projects_path = Path(projects_path)
            if not projects_path.exists():
                projects_path.mkdir()
            self.projects_path = projects_path

    def reload_graph_config(self):
        """Reloads the graph configuration file."""
        # Create config if nonexistent
        if not self.config_path.exists():
            with open(self.config_path, mode='wb') as cfg:
                cfg.write(self._config_template)

        # Validate config
        with self.config_path.open(mode='r') as f:
            graph_config = yaml.load(f)

            # Check for inequality between cache and loaded config
            # Used to skip expensive config schema validation
            # trivial check + equality check
            if (len(graph_config.keys()) != len(self._config_cache.keys())) or (
                    graph_config != self._config_cache):
                validate_config(graph_config)
                self._config_cache = graph_config

            template_load = yaml.load(self._config_template)
            if graph_config['CONFIG_VER'] != template_load['CONFIG_VER']:
                raise ValueError(
                    f'Config version mismatch! Delete the old configuration file to regenerate {graph_config["CONFIG_VER"]=} {template_load["CONFIG_VER"]=}')

        if graph_config['GRAPHVIZ'] != 'path':
            if Path(graph_config['GRAPHVIZ']).exists() and Path(graph_config['GRAPHVIZ']).is_dir():
                os.environ["PATH"] += os.pathsep + str(Path(graph_config['GRAPHVIZ']))
            else:
                raise FileNotFoundError(
                    f'The Graphviz binaries path does not exist: "{graph_config["GRAPHVIZ"]}"')
        self.graph_config = graph_config

    def log(self, msg, level=logging.DEBUG):
        """Logging method for gregtech.flow.

        Args:
            msg (str): The message
            level (logging.DEBUG, logging.INFO, etc., optional): Logging level. Defaults to logging.DEBUG.
        """
        log = self.logger
        log.log(level, f'{msg}')

    def create_graph(self, project_name: Path | str) -> None:
        """Centralized graph creation function. Also checks if the project exists or not.

        Args:
            project_name (Path | str): The project's path
        """
        # Standardize the project's name by forcing the suffix to be .yaml
        project_name = Path(project_name)
        if project_name.suffix == '':
            project_name = project_name.with_suffix('.yaml')
        elif project_name.suffix != '.yaml':
            raise ValueError(f'Invalid project extension: {project_name}')

        project_relpath = self.projects_path / project_name

        # Check existence
        if not project_relpath.exists():
            raise FileNotFoundError(f'The specified project "{project_name}" could not be found!')

        title = ''
        with project_relpath.open(mode='r') as f:
            doc_load = list(yaml.load_all(f))
            if len(doc_load) == 2:  # Check if has GT: Flow header
                header = doc_load[0]
                validate_header(header)
                title = header['title']
                self.log(
                    f'Current project: "{title}" by [bright_green]{header["creator"]}',
                    logging.INFO)
            elif len(doc_load) == 1:
                self.log(f'Current project: "{project_name}"', logging.INFO)
            else:
                raise ValueError(f'Found {len(doc_load)} YAML documents in 1 project!')

        recipes = load_project(
            project_name, self.graph_config, self.projects_path)

        if project_name.suffix == '.yaml':
            project_name = project_name.with_suffix('')

        equations_solver(
            self, project_name, recipes, title)

    def create_filetree(self,
                        path: Path,
                        pfx: str = '',
                        max_depth: int = 720,
                        emoji: bool = True) -> Iterator[str]:
        """Creates a file tree of the input path.

        Args:
            path (Path): Path of the directory
            pfx (str, optional): Prefix. Defaults to ''.
            max_depth (int, optional): Recursion limit of the function. Defaults to 720 (arbitrary).
            emoji (bool, optional): Whether or not to use emojis. Defaults to True.

        Yields:
            Iterator[str]t: Lines of the file tree
        """
        if max_depth <= 0:
            raise RecursionError('Exceeded set recursion limit of 720!')
        # fmt: off
        space =  '    '  # noqa
        branch = '│   '  # noqa
        tee =    '├── '  # noqa
        last =   '└── '  # noqa
        # fmt: on

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
                yield from self.create_filetree(path, f'{pfx}{extension}', max_depth=max_depth - 1)

    def interactive_cli(self, once: bool = False) -> None:
        """The interactive CLI for GT: Flow."""
        @contextlib.contextmanager
        def print_encase(cs: Console, title: str | Literal['latest.log'], *, confirm: bool = False):
            """Prints a horizontal rule below and above. Also needs a title."""
            if (not self.quiet) or (title != 'latest.log'):
                cs.print()
                cs.print(
                    Rule(style='bright_white',
                         title=f'[bold bright_white]{title}',
                         align='center'))
                yield
                cs.print(Rule(style='bright_white'))
                if confirm:
                    input()
                else:
                    cs.print()
            else:
                yield
                cs.print()

        # <-- Setup -->
        self.running_from = 'INTERACTIVE'
        reserved_lines = shutil.get_terminal_size().lines - 12
        prompt_session: PromptSession = PromptSession(completer=PathCompleter(directory=self.projects_path),
                                                      style=Style.from_dict(
                                                          {'bigger_than': '#ffffff'}),
                                                      complete_style=CompleteStyle.COLUMN,  # Use UP and DOWN
                                                      reserve_space_for_menu=min(
                                                      8, max(0, reserved_lines)),  # 0 <= lines <= 8
                                                      enable_history_search=False,
                                                      complete_while_typing=True)

        # <-- Constants -->
        flow_red = '#ff6961'
        flow_yellow = '#f8f38d'
        flow_teal = '#08cad1'
        flow_purple = '#7253ed'

        highlight = '#a5e075'

        # <-- Rich components -->
        # The header
        header = Layout(
            Panel(
                Align(
                    f'[bold {flow_purple} link=https://velolib.github.io/gregtech-flow/]GT: Flow Interactive CLI[/]',
                    align='center',
                    vertical='middle'),
                border_style=f'bold {flow_purple}'),
            name='header',
            size=3)

        # guide.txt
        guide_text = Group(f'[{highlight}]Please enter project path (example: "[underline]power/oil/light_fuel.yaml[/]")[/]',
                           Rule(style=flow_teal),
                           inspect.cleandoc(f'''\
                                             [bright_white bold]Valid commands:[/]
                                             [bright_white]- [/][{highlight}]end[/][bright_white] / [/][{highlight}]stop[/][bright_white] / [/][{highlight}]exit[/][bright_white]: Stop the program[/]
                                             [bright_white]- [/][{highlight}]all[/][bright_white]: Select all files for graph creation[/]
                                             [bright_white]- [/][{highlight}]last[/][bright_white]: The last project inputted (or just input nothing)[/]
                                             [bright_white]- [/][{highlight}]tree[/][bright_white]: Prints the "[underline]projects/[/underline]" file tree[/]'''))

        guide = Layout(
            Panel(
                guide_text,
                border_style=f'bold {flow_teal}',
                title='guide.txt',
                title_align='left'),
            name='guide')

        # links.md
        links_text = inspect.cleandoc(f'''\
                                       [{highlight}]GitHub Repository[/][bright_white]: [/][underline bright_cyan link=https://github.com/velolib/gregtech-flow]https://github.com/velolib/gregtech-flow[/]
                                       [{highlight}]Website[/][bright_white]          : [/][underline bright_cyan link=https://velolib.github.io/gregtech-flow/]https://velolib.github.io/gregtech-flow[/]''')
        links = Layout(
            Panel(
                links_text,
                border_style=f'bold {flow_yellow}',
                title='links.md',
                title_align='left'),
            name='links')

        # license.txt
        license = Layout(
            Panel(
                inspect.cleandoc(f'''
                                  [bold bright_white underline link=https://github.com/velolib/gregtech-flow/blob/master/LICENSE.txt]MIT License[/]
                                  [{flow_purple} underline link=https://github.com/velolib/gregtech-flow]gregtech-flow[/][{highlight}][bright_white]:[/bright_white] Copyright (c) 2023[/] [{flow_purple} underline link=https://github.com/velolib]velolib[/]
                                  [{flow_yellow} underline link=https://github.com/OrderedSet86/gtnh-flow]gtnh-flow[/]    [{highlight}][bright_white]:[/bright_white] Copyright (c) 2022[/] [{flow_yellow} underline link=https://github.com/OrderedSet86]OrderedSet86[/]'''),
                border_style=f'bold {flow_red}',
                title='license.txt',
                title_align='left'),
            name='license')

        # Interface (everything combined)
        interface = Layout()
        interface.size = 4

        interface.split_column(header, Layout(name='content', size=9))

        interface['content'].split_row(guide, Layout(name='right_sect'))

        interface['content']['right_sect'].split_column(links, license)

        console = Console(height=12, soft_wrap=True)

        try:
            while True:
                console.print(interface)
                sel_option = prompt_session.prompt([('class:bigger_than', '> ')])

                match sel_option:
                    case 'end' | 'stop' | 'exit':
                        sys.exit(0)
                    case 'all':
                        with print_encase(console, 'latest.log'):
                            self.logger.info(f'Getting config from: "{self.config_path}"')
                            for proj in Path(self.projects_path).glob('**/*.yaml'):
                                if Path(self.projects_path, 'dev') not in proj.parents:
                                    self.create_graph(proj.relative_to(self.projects_path))
                    case 'last' | '':
                        with print_encase(console, 'latest.log'):
                            self.logger.info(f'Getting config from: "{self.config_path}"')
                            self.create_graph(self._project_cache)
                    case 'tree':
                        with print_encase(console, 'tree.txt', confirm=True):
                            for x in self.create_filetree(Path(self.projects_path)):
                                console.print(x)
                    case _:
                        with print_encase(console, 'latest.log'):
                            self.logger.info(f'Getting config from: "{self.config_path}"')
                            self.create_graph(sel_option)
                        self._project_cache = sel_option
                if once:
                    sys.exit(0)
                self.reload_graph_config()
        except Exception as exc:
            exc.add_note(self.running_from)
            raise

    def direct_cli(self, path: Path) -> None:
        """Direct CLI implementation for GT: Flow.

        Args:
            path (Path): The path inputted from the command line
        """
        self.running_from = 'DIRECT'
        if not self.quiet:
            rprint(
                Panel(
                    Align(
                        '[bold #7253ed link=https://velolib.github.io/gregtech-flow/]GT: Flow Direct CLI[/]',
                        align='center',
                        vertical='middle'),
                    border_style='bold #7253ed'))
            self.logger.info(f'Getting config from: "{self.config_path}"')
        try:
            self.create_graph(str(path))
        except Exception as exc:
            exc.add_note(self.running_from)
            raise

    def _run_typer(self,
                   path: Optional[Path] = typer.Argument(
                       None, help='Project path relative to ./projects'),
                   quiet: Optional[bool] = typer.Option(
                       False, '--quiet', '-q', help='Disable logging'),
                   config: Optional[Path] = typer.Option(None, help='Configuration file path'),
                   once: bool = typer.Option(False, help='Only run Interactive CLI once')):
        """For typer."""
        if quiet:
            self.logger.setLevel(logging.CRITICAL + 1)
        self.quiet = bool(quiet)

        if config:
            config = Path(config).absolute()
            if config.is_file() and config.exists():
                self.config_path = Path(config).resolve()
            else:
                raise FileNotFoundError(
                    f'Specified configuration path "{config}" is invalid or does not exist.')

        if path is None:
            self.interactive_cli(once=once)
        else:
            self.direct_cli(path)
            sys.exit(0)

    def run(self) -> None:
        """Runs the CLI."""
        typer.run(self._run_typer)


def run_cli():
    """Runs the CLI."""
    cli = ProgramContext()
    cli.run()


if __name__ == '__main__':
    run_cli()
