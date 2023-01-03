import pkgutil
import os

print(os.getcwd())


def data():
    dt = pkgutil.get_data('gtnhvelo', 'resources/overclock_data.yaml')
    return dt
