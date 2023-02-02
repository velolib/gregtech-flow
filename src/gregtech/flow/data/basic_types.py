import logging
import textwrap
import typing
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass  # type: ignore
class Ingredient:
    """
    Ingredient class for recipes.

    Args:
        name (str): Ingredient name
        quant (float): Ingredient quantity
    """
    name: str
    quant: float
    # Used to track deprecation.
    found_bracket_warning: typing.ClassVar[bool] = field(init=False, default=0)  # type: ignore

    # NOTE: Too lazy to implement, just replace () to [].
    def __post_init__(self) -> None:
        logger = logging.getLogger('rich')
        first_word = self.name.split(' ')[0]
        if not self.__class__.found_bracket_warning and '[' in first_word and ']' in first_word:
            logger.warning(textwrap.dedent('''\
                You are using square brackets in your I/O!
                Support for square bracket tags "[]" will be phased out in the future.
                Switch to using parentheses "()" instead.'''))
            self.__class__.found_bracket_warning = True
        if self.name not in {"EU"} and self.name.casefold() != self.name:
            raise DeprecationWarning(textwrap.dedent(f'''\
                You are using uppercase characters in your I/O ({self.name})!
                Most characters will be lowercased, so switch to using unique I/O names or just use lowercase characters!
                The program will not be able to run if you keep using uppercase characters.
                                                     '''))
        self.name = self.name.casefold().replace('(', '[', 1).replace(')', ']', 1)


class IngredientCollection:
    def __init__(self, *ingredient_list: Ingredient):
        """
        Ingredient collection class for recipes. Used for I/O.

        Args:
            *ingredient list: Variable length ingredient list
        """
        self._ings = ingredient_list
        # Note: name is not a unique identifier for multi-input situations
        # therefore, need to defaultdict a list
        self._ingdict = defaultdict(list)
        for ing in self._ings:
            self._ingdict[ing.name].append(ing.quant)
        # self._ingdict = {x.name: x.quant for x in self._ings}

    def __iter__(self):
        return iter(self._ings)

    def __getitem__(self, idx):
        if isinstance(idx, int):
            return self._ings[idx]
        elif isinstance(idx, str):
            return self._ingdict[idx]
        else:
            raise RuntimeError(f'Improper access to {self} using {idx}')

    def __repr__(self):
        return str([x for x in self._ings])

    def __mul__(self, mul_num):
        for ing in self._ings:
            ing.quant *= mul_num
        self._ingdict = defaultdict(list)
        for ing in self._ings:
            self._ingdict[ing.name].append(ing.quant)
        # self._ingdict = {x.name: x.quant for x in self._ings}

        return self

    def __len__(self):
        return len(self._ings)


class Recipe:
    def __init__(
        self,
        machine_name: str,
        user_voltage: str,
        inputs: IngredientCollection,
        outputs: IngredientCollection,
        eut: int,
        dur: float | int,
        circuit=0,
        **kwargs
    ):
        """
        Recipe glass for GT: Flow

        Args:
            machine_name (str): Machine name
            user_voltage (str): Selected user voltage
            inputs (IngredientCollection): Inputs wrapped in an IngredientCollection class
            outputs (IngredientCollection): Outputs wrapped in an IngredientCollection class
            eut (int): The EU in EU/t
            dur (float | int): Duration in ticks
            circuit (int, optional): Circuit number. Defaults to 0. Unused for now
        """
        self.machine = machine_name
        self.user_voltage = user_voltage
        self.I = inputs
        self.O = outputs
        self.eut = eut
        self.dur = dur
        self.circuit = circuit
        self.multiplier = -1
        self.base_eut = eut  # Used for final graph output
        for key, value in kwargs.items():
            match key:  # for type checking
                case 'target':
                    self.target = value
                case _:
                    setattr(self, key, value)

    def __repr__(self):
        return str([f'{x}={getattr(self, x)}' for x in vars(self)])

    def __mul__(self, mul_num: int):
        assert self.multiplier == -1, 'Cannot multiply recipe multiple times'

        self.I *= mul_num
        self.O *= mul_num
        self.eut *= mul_num
        self.multiplier = mul_num

        return self
