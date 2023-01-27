import yaml
import pkgutil
import jsonschema

voltages = yaml.safe_load(pkgutil.get_data('gregtech.flow', 'resources/data.yaml')  # type: ignore
                          )['overclock_data']['voltage_data']['tiers']


def validate_config(config: dict):
    schema_load = yaml.safe_load(pkgutil.get_data('gregtech.flow', 'resources/config_schema.json'))  # type: ignore
    jsonschema.validate(instance=config, schema=schema_load)


def main():
    pass


if __name__ == '__main__':
    main()
