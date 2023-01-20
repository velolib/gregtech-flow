from enum import StrEnum, auto, EnumMeta


class MetaEnum(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        return True


class ContainsStrEnum(StrEnum, metaclass=MetaEnum):
    pass


class OutputFormat(ContainsStrEnum):
    svg = auto()
    png = auto()
    jpg = auto()
    jpeg = auto()
    pdf = auto()


class Orientation(ContainsStrEnum):
    TB = 'TB'
    LR = 'LR'
    BT = 'BT'
    RL = 'RL'


class LineStyle(ContainsStrEnum):
    line = auto()
    spline = auto()
    polyline = auto()
    curved = auto()


if __name__ == '__main__':
    print(OutputFormat['svg'])
    print(OutputFormat.jpeg)
    print('sVg' in OutputFormat)
    print(Orientation.RL)
