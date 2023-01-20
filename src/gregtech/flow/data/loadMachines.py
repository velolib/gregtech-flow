from pathlib import Path

import yaml

from gregtech.flow.data.basicTypes import Ingredient, IngredientCollection, Recipe


def standardizeMachineName(name):
    replacements = {
        'lgt': 'large gas turbine',

        'lcr': 'large chemical reactor',

        'ebf': 'electric blast furnace',
        'blast furnace': 'electric blast furnace',

        'xlgt': 'XL Turbo Gas Turbine',

        'cal': 'circuit assembly line',

        'fusion': 'fusion reactor',

        'xlst': 'XL Turbo Steam Turbine',

        'lst': 'large steam turbine',

        'ico': 'industrial coke oven',

        'exxonmobil': 'chemical plant',
        'chem plant': 'chemical plant',

        'tgs': 'tree growth simulator',

        'utupu tanuri': 'industrial dehydrator',
        'utupu-tanuri': 'industrial dehydrator',

        'floation cell': 'floation cell regulator',

        'isamill': 'isamill grinding machine',

        'high current industrial arc furnace': 'industrial arc furnace',

        'lpf': 'large processing factory',

        'industrial mixer': 'industrial mixing machine',

        'industrial thermal centrifuge': 'large thermal refinery',

        'industrial rock breaker': 'boldarnator',

        'xl turbo steam turbine': 'XL Turbo Steam Turbine',
        'xl steam turbine': 'XL Turbo Steam Turbine',
        'xl turbo gas turbine': 'XL Turbo Gas Turbine',
        'xl gas turbine': 'XL Turbo Gas Turbine',
    }

    if name in replacements:
        return replacements[name]
    else:
        return name


def recipesFromConfig(project_name, graph_config, project_folder: str | Path = 'projects'):
    # Load config file
    PROJECT_FILE_PATH = Path(project_folder) / f'{project_name}'
    project_name = PROJECT_FILE_PATH.name.split('.')[0]
    with open(PROJECT_FILE_PATH, 'r') as f:
        project = list(yaml.safe_load_all(f))[-1]

    # Prep recipes for graph
    recipes = []
    for rec in project:
        if graph_config.get('DUR_FORMAT', 'ticks') == 'sec':
            rec['dur'] *= 20

        machine_name = rec['m'].lower()
        machine_name = standardizeMachineName(machine_name)

        recipes.append(
            Recipe(
                machine_name,
                rec['tier'].lower(),
                IngredientCollection(*[Ingredient(name, quant) for name, quant in rec['I'].items()]),
                IngredientCollection(*[Ingredient(name, quant) for name, quant in rec['O'].items()]),
                rec['eut'],
                rec['dur'],
                **{x: rec[x] for x in rec.keys() if x not in {'m', 'I', 'O', 'eut', 'dur', 'tier'}},
            )
        )

    return recipes
