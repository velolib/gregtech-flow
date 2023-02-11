"""JSON Schema validators for the GT: Flow projects and the configuration file."""

from __future__ import annotations

import pkgutil

import fastjsonschema  # type: ignore
import ruamel.yaml as ruamel  # type: ignore

yaml = ruamel.YAML(typ='safe', pure=True)


def validate_config(loaded: dict) -> bool:
    """Validates the configuration dictionary inputted.

    Args:
        loaded (dict): Configuration file as a dictionary

    Returns:
        bool: True
    """
    schema_load = fastjsonschema.compile(yaml.load(pkgutil.get_data(
        'gregtech.flow', 'resources/config_schema.json')))  # type: ignore
    schema_load(loaded)
    return True


def validate_project(loaded: list) -> bool:
    """Validates the loaded project content YAML inputted.

    Args:
        loaded (list): Loaded project content YAML as a list

    Returns:
        bool: True
    """
    schema_load = fastjsonschema.compile(yaml.load(pkgutil.get_data(
        'gregtech.flow', 'resources/project_schema.json')))  # type: ignore
    schema_load(loaded)
    return True


def validate_header(loaded: dict) -> bool:
    """Validates the loaded project header YAML inputted.

    Args:
        loaded (dict): Loaded project header YAML as a dict

    Returns:
        bool: True
    """
    schema_load = fastjsonschema.compile(yaml.load(pkgutil.get_data(
        'gregtech.flow', 'resources/header_schema.json')))  # type: ignore
    schema_load(loaded)
    return True
