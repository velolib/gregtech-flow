import re
from schema import Schema, And, Or  # type: ignore
from gregtech.flow.config.enums import OutputFormat, Orientation, LineStyle
from pathlib import Path
import pkgutil
import yaml

voltages = yaml.safe_load(pkgutil.get_data('gregtech.flow', 'resources/data.yaml')  # type: ignore
                          )['overclock_data']['voltage_data']


def is_hex_color(value):
    """
    Check if valid hex color string
    """
    return re.search(r'^#(?:[0-9a-fA-F]{1,2}){3}$', value)


def is_graphviz_color(value):  # TODO: Graphviz colors enum
    """
    Check if valid hex color string or a valid graphviz color definition
    """
    result = True if is_hex_color(value) or isinstance(value, str) else False
    return result


config_schema = Schema({
    'CONFIG_VER': int,
    'GRAPHVIZ': Or(str, lambda z: Path(z).exists()),
    'POWER_LINE': bool,
    'DO_NOT_BURN': And(list, lambda z: all(isinstance(item, str) for item in z)),
    'OUTPUT_FORMAT': lambda z: z in OutputFormat,
    'USE_RAINBOW_EDGES': bool,
    'DUR_FORMAT': lambda z: z in ('sec', 'ticks'),
    'VIEW_ON_COMPLETION': bool,
    'PRINT_BOTTLENECKS': bool,
    'USE_BOTTLENECK_EXACT_VOLTAGE': bool,
    'BOTTLENECK_MIN_VOLTAGE': str,
    'MAX_BOTTLENECKS': int,
    'GENERAL_FONT': str,
    'SUMMARY_FONT': str,
    'GROUP_FONT': str,
    'TITLE_FONT': str,
    'NODE_FONTSIZE': int,
    'EDGE_FONTSIZE': int,
    'GROUP_FONTSIZE': int,
    'TITLE_FONTSIZE': int,
    'BACKGROUND_COLOR': is_graphviz_color,
    'TITLE_COLOR': is_graphviz_color,
    'SUMMARY_COLOR': is_graphviz_color,
    'EDGECOLOR_CYCLE': And(list, lambda z: all(is_hex_color(item) for item in z)),
    'SOURCESINK_COLOR': is_graphviz_color,
    'NONLOCKEDNODE_COLOR': is_graphviz_color,
    'LOCKEDNODE_COLOR': is_graphviz_color,
    'POSITIVE_COLOR': is_graphviz_color,
    'NEGATIVE_COLOR': is_graphviz_color,
    'POWER_UNITS': Or(lambda z: z in ('auto', 'eut'), lambda z: z in voltages),  # (eut, auto, lv, mv, etc.)
    'ORIENTATION': lambda z: z in Orientation,
    'LINE_STYLE': lambda z: z in LineStyle,
    'RANKSEP': And(str, lambda z: z.replace('.', '', 1).isdigit()),  # str(float)
    'NODESEP': And(str, lambda z: z.replace('.', '', 1).isdigit()),  # str(float)
    'COMBINE_INPUTS': bool,
    'COMBINE_OUTPUTS': bool,
    'DEBUG_LOGGING': bool,
    'DEBUG_SHOW_EVERY_STEP': bool,
    'SHOW_MACHINE_INDICES': bool,
    'STRIP_BRACKETS': bool,
})

if __name__ == '__main__':
    import time
    start = time.perf_counter()
    load = yaml.safe_load(pkgutil.get_data('gregtech.flow', 'resources/config_template.yaml'))  # type: ignore
    print(load)
    config_schema.validate(load)
    print(f'Done in {time.perf_counter() - start}')
