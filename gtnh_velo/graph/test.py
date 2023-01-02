import pkgutil

data = pkgutil.get_data(__name__, 'resources/misc.yaml')

print(data)