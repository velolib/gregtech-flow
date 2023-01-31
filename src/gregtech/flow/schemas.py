import ruamel.yaml as ruamel  # type: ignore
import pkgutil
import jsonschema

yaml = ruamel.YAML(typ='safe', pure=True)


class Validator:
    @staticmethod
    def validate_config(config: dict):
        schema_load = yaml.load(pkgutil.get_data(
            'gregtech.flow', 'resources/config_schema.json'))  # type: ignore
        jsonschema.validate(instance=config, schema=schema_load)

    @staticmethod
    def validate_project(project: list):
        schema_load = yaml.load(pkgutil.get_data(
            'gregtech.flow', 'resources/project_schema.json'))  # type: ignore
        jsonschema.validate(instance=project, schema=schema_load)


def main():
    pass


if __name__ == '__main__':
    main()
