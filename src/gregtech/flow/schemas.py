"""JSON Schema validators for the GT: Flow projects and the configuration file."""

import pkgutil

import jsonschema
import ruamel.yaml as ruamel  # type: ignore

yaml = ruamel.YAML(typ='safe', pure=True)


def validate_config(config: dict) -> bool:
    """Validates the configuration dictionary inputted.

    Args:
        config (dict): Configuration file as a dictionary

    Returns:
        bool: True
    """
    schema_load = yaml.load(pkgutil.get_data(
        'gregtech.flow', 'resources/config_schema.json'))  # type: ignore
    jsonschema.validate(instance=config, schema=schema_load)
    return True


def validate_project(project: list) -> bool:
    """Validates the loaded project YAML inputted.

    Args:
        project (list): Loaded project YAML as a list

    Returns:
        bool: True
    """
    schema_load = yaml.load(pkgutil.get_data(
        'gregtech.flow', 'resources/project_schema.json'))  # type: ignore
    jsonschema.validate(instance=project, schema=schema_load)
    return True
