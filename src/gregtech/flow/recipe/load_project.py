"""Module used to load recipes from a GT: Flow project."""

from __future__ import annotations

from pathlib import Path

from gregtech.flow.recipe.basic_types import (Ingredient, IngredientCollection,
                                              Recipe)
from gregtech.flow.schemas import validate_project, yaml


def unalias_machine_name(name: str) -> str:
    """Used to turn machine name aliases into their standard form used for comparisons in the code.

    Args:
        name (str): Machine name

    Returns:
        str: Standardized machine name
    """
    aliases = {
        # <-- CAL --> #
        'cal': 'circuit assembly line',

        # <-- Chemplant --> #
        'chem plant': 'chemical plant',
        'exxonmobil': 'chemical plant',

        # <-- Electric Blast Furnace --> #
        'ebf': 'electric blast furnace',
        'blast furnace': 'electric blast furnace',

        # <-- Industrials --> #
        'industrial mixer': 'industrial mixing machine',
        'industrial rock breaker': 'boldarnator',
        'industrial thermal centrifuge': 'large thermal refinery',

        # <-- Isamill --> #
        'isamill': 'isamill grinding machine',

        # <-- Large X Y --> #
        'lcr': 'large chemical reactor',
        'lpf': 'large processing factory',

        # <-- TGS --> #
        'tgs': 'tree growth simulator',

        # <-- Industrial Dehydrator --> #
        'utupu tanuri': 'industrial dehydrator',
        'utupu-tanuri': 'industrial dehydrator',

        # <-- Turbines --> #
        'xl gas turbine': 'XL Turbo Gas Turbine',
        'xl steam turbine': 'XL Turbo Steam Turbine',
        'xl turbo gas turbine': 'XL Turbo Gas Turbine',
        'xl turbo steam turbine': 'XL Turbo Steam Turbine',
        'lgt': 'large gas turbine',
        'lst': 'large steam turbine',
        'xlgt': 'XL Turbo Gas Turbine',
        'xlst': 'XL Turbo Steam Turbine',

        # <-- No category --> #
        'flotation cell': 'flotation cell regulator',

        'fusion': 'fusion reactor',

        'high current industrial arc furnace': 'industrial arc furnace',

        'ico': 'industrial coke oven',
    }

    return aliases.get(name, name)


def load_project(project_name: str | Path, graph_config: dict,
                 project_dir: str | Path = 'projects') -> list:
    """Loads the inputted project and returns a list of Recipe objects.

    Args:
        project_name (str | Path): Project name relative to project_folder
        graph_config (dict): Graph config as a dict
        project_dir (str | Path, optional): Project directory. Defaults to 'projects'

    Returns:
        list: Loaded project
    """
    # Load config file
    project_filepath = Path(project_dir) / f'{project_name}'
    project_name = project_filepath.name.split('.')[0]
    with open(project_filepath) as f:
        project = list(yaml.load_all(f))[-1]
        validate_project(project)

    # Create recipe objects for graph
    recipes = []
    for rec in project:
        if graph_config.get('DUR_FORMAT', 'ticks') == 'sec':
            rec['dur'] *= 20

        machine_name = rec['m'].casefold()
        machine_name = unalias_machine_name(machine_name)

        recipes.append(
            Recipe(
                machine_name,
                rec['tier'].casefold(),
                IngredientCollection(*[Ingredient(name, quant)
                                     for name, quant in rec['I'].items()]),
                IngredientCollection(*[Ingredient(name, quant)
                                     for name, quant in rec['O'].items()]),
                rec['eut'],
                rec['dur'],
                **{x: (rec[x].casefold() if isinstance(rec[x], str) else rec[x]) for x in rec.keys() if x not in {'m', 'I', 'O', 'eut', 'dur', 'tier'}},
            )
        )

    return recipes
