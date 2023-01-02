# Standard libraries
import logging
import os
import sys
import argparse
from pathlib import Path

# Pypi libraries
import yaml
from rich import print as rprint
from rich.logging import RichHandler
from rich.panel import Panel
from rich.console import Console, group
from rich.text import Text

# Internal libraries
from prototypes.linearSolver import systemOfEquationsSolverGraphGen
from src.graph import Graph
from src.data.loadMachines import recipesFromConfig

# Conditional imports based on OS
try: # Linux
    import readline
except Exception: # Windows
    import pyreadline3 as readline

import os
os.environ["PATH"] += os.pathsep + 'C:/Program Files/Graphviz/bin'


class ProgramContext:


    def __init__(self):
        with open('config_factory_graph.yaml', 'r') as f:
            graph_config = yaml.safe_load(f)
        
        LOG_LEVEL = logging.INFO
        if graph_config['DEBUG_LOGGING']:
            LOG_LEVEL = logging.DEBUG
        logging.basicConfig(handlers=[RichHandler(level=LOG_LEVEL, markup=True)], format='%(message)s', datefmt='[%X]', level='NOTSET')

    @staticmethod
    def cLog(msg, level=logging.DEBUG):
        # Not sure how to level based on a variable, so just if statements for now
        log = logging.getLogger('rich')
        if level == logging.DEBUG:
            log.debug(f'{msg}')
        elif level == logging.INFO:
            log.info(f'{msg}')
        elif level == logging.WARNING:
            log.warning(f'{msg}')

    
    def run(self, graph_gen=None):
        if graph_gen == None:
            graph_gen = self.standardGraphGen

        with open('config_factory_graph.yaml', 'r') as f:
            graph_config = yaml.safe_load(f)
        
        if graph_config['USE_NEW_SOLVER']:
            graph_gen = systemOfEquationsSolverGraphGen
        
        # Set up autcompletion config
        projects_path = Path('projects')
        readline.parse_and_bind('tab: complete')
        readline.set_completer_delims('')

        def completer(text, state):
            prefix = ''
            suffix = text
            if '/' in text:
                parts = text.split('/')
                prefix = '/'.join(parts[:-1])
                suffix = parts[-1]

            target_path = projects_path / prefix
            valid_tabcompletes = os.listdir(target_path)
            valid_completions = [x for x in valid_tabcompletes if x.startswith(suffix)]
            if state < len(valid_completions): # Only 1 match
                completion = valid_completions[state]
                if prefix != '':
                    completion = ''.join([prefix, '/', completion])
                if not completion.endswith('.yaml'):
                    completion += '/'
                return completion
            else:
                return None
            
        
        def create_graph(project_name):
            if not project_name.endswith('.yaml'):
                # Assume when the user wrote "power/fish/methane", they meant "power/fish/methane.yaml"
                # This happens because autocomplete will not add .yaml if there are alternatives (like "power/fish/methane_no_biogas")
                project_name += '.yaml'
            
            project_relpath = projects_path / f'{project_name}'
            
            if project_relpath.exists():
                title = None
                with project_relpath.open(mode='r') as f:
                    doc_load = list(yaml.safe_load_all(f))
                    if len(doc_load) >= 2: 
                        metadata = doc_load[0]
                        title = metadata['title']
                
                recipes = recipesFromConfig(project_name)

                if project_name.endswith('.yaml'):
                    project_name = project_name[:-5]

                graph_gen(self, project_name, recipes, graph_config, title)
                print('')
            else:
                rprint('\n[bright_red]Error: Project could not be found\n')

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
            # Interactive selector
            if not len(sys.argv) > 1:
                readline.set_completer(completer)
                rprint(Panel(get_elements()))
                rprint('[bright_white]> ', end='')
                ip = input()
                if ip.casefold() == 'end':
                    exit()
                create_graph(ip)
            
            # CLI Selector
            else:
                parser = argparse.ArgumentParser(description='Input project path')
                parser.add_argument('project_path')
                
                parser.add_argument('format_override', nargs='?', choices=['png', 'pdf'], default=None)
                args = parser.parse_args()
                if args.format_override:
                    graph_config['OUTPUT_FORMAT'] = args.format_override
                
                create_graph(args.project_path)
                break


    @staticmethod
    def standardGraphGen(self, project_name, recipes, graph_config, title=None):
        # Create graph and render
        g = Graph(project_name, recipes, self, graph_config=graph_config, title=title)
        g.connectGraph()
        g.balanceGraph()
        g.outputGraphviz()


if __name__ == '__main__':
    console = Console()
    console.print(Panel('[bright_blue]gtnh-velo', expand=False))
    pc = ProgramContext()
    pc.run()