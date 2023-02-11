"""Class abstractions for GT: Flow projects."""

from __future__ import annotations

import inspect
from collections import defaultdict
from dataclasses import dataclass
from functools import singledispatchmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass  # type: ignore
class Ingredient:
    """Ingredient class for recipes.

    Args:
        name (str): Ingredient name
        quant (float): Ingredient quantity
    """
    name: str
    quant: float

    # NOTE: Too lazy to implement, just replace () to [].
    def __post_init__(self) -> None:
        """Catches deprecations after constructing an Ingredient object.

        Raises:
            DeprecationWarning: A feature or attribute of this Ingredient is deprecated.
        """
        first_word = self.name.split(' ')[0]
        if '[' in first_word and ']' in first_word:
            raise DeprecationWarning(inspect.cleandoc('''You are using square brackets in your I/O!
                                                        Support for square bracket tags "[]" will be phased out in the future.
                                                        Switch to using parentheses "()" instead.'''))
        if self.name not in {"EU"} and self.name.casefold() != self.name:
            raise DeprecationWarning(inspect.cleandoc(f'''You are using uppercase characters in your I/O ({self.name})!
                                                        Most characters will be lowercased, so switch to using unique I/O names or just use lowercase characters!
                                                        The program will not be able to run if you keep using uppercase characters.'''))


class IngredientCollection:
    """Collection of Ingredients with modified magic methods."""

    def __init__(self, *ingredient_list: Ingredient):
        """Ingredient collection class for recipes. Used for I/O.

        Args:
            *ingredient list: Variable length ingredient list
        """
        self._ings: tuple[Ingredient, ...] = ingredient_list
        # Note: name is not a unique identifier for multi-input situations
        # therefore, need to defaultdict a list
        self._ingdict = defaultdict(list)
        for ing in self._ings:
            self._ingdict[ing.name].append(ing.quant)
        # self._ingdict = {x.name: x.quant for x in self._ings}

    def __iter__(self) -> Iterator[Ingredient]:
        """This method is called when an iterator is required for a container.

        Returns an Iterator of the Ingredients in this IngredientCollection.
        """
        return iter(self._ings)

    @singledispatchmethod
    def __getitem__(self, idx) -> list:
        """Getitem method."""
        raise TypeError(f'Invalid index type: {type(idx)}({idx})')

    @__getitem__.register  # type: ignore [arg-type]
    def _(self, idx: str) -> list[float]:
        """Called to implement evaluation of self[key].

        Args:
            idx (str): An Ingredient's name

        Raises:
            RuntimeError: Improper access. (type error)

        Returns:
            list[float]: An Ingredient's quantity in a list
        """
        if isinstance(idx, str):
            return self._ingdict[idx]
        else:
            raise TypeError(f'Improper access to {self} using {idx}')

    @__getitem__.register  # type: ignore [arg-type]
    def _(self, idx: int) -> Ingredient:
        """Called to implement evaluation of self[key].

        Args:
            idx (int): Integer index

        Raises:
            RuntimeError: Improper access. (type error)

        Returns:
            Ingredient: An Ingredient in this IngredientCollection.
        """
        if isinstance(idx, int):
            return self._ings[idx]
        else:
            raise TypeError(f'Improper access to {self} using {idx}')

    def __repr__(self) -> str:
        """Returns an "official" string representation of this IngredientCollection."""
        return str(list[self._ings])  # type: ignore [name-defined]

    # TODO: Type hint Self as return value when mypy supports it.
    def __mul__(self, mul_num: float | int):
        """Arithmetic operation for *.

        Multiplies the quantities of the Ingredients in this IngredientCollection.
        """
        for ing in self._ings:
            ing.quant *= mul_num
        self._ingdict = defaultdict(list)
        for ing in self._ings:
            self._ingdict[ing.name].append(ing.quant)
        # self._ingdict = {x.name: x.quant for x in self._ings}

        return self

    def __len__(self) -> int:
        """Called to implement the built-in function len()."""
        return len(self._ings)


class Recipe:
    """Recipe class abstraction for GT: Flow projects."""

    def __init__(self,
                 machine_name: str,
                 user_voltage: str,
                 inputs: IngredientCollection, outputs: IngredientCollection,
                 eut: int, dur: float | int,
                 circuit=-1,
                 **kwargs):
        """Recipe class constructor.

        Args:
            machine_name (str): Machine name
            user_voltage (str): Selected user voltage
            inputs (IngredientCollection): Inputs wrapped in an IngredientCollection class
            outputs (IngredientCollection): Outputs wrapped in an IngredientCollection class
            eut (int): The EU in EU/t
            dur (float | int): Duration in ticks. Will be converted to float.
            circuit (int, optional): Circuit number. Defaults to -1 (None).
        """
        self.machine = machine_name
        self.user_voltage = user_voltage
        self.I = inputs
        self.O = outputs
        self.eut = eut
        self.dur = float(dur)
        self.circuit = circuit
        self.multiplier = -1
        self.base_eut = eut  # Used for final graph output
        for key, value in kwargs.items():
            match key:  # for type checking
                case 'target':
                    self.target = value
                case _:
                    setattr(self, key, value)

    def __repr__(self) -> str:
        """Returns an "official" string representation of this Recipe."""
        return str([f'{x}={getattr(self, x)}' for x in vars(self)])

    def __mul__(self, mul_num):  # TODO: Type hint Self when mypy supports it.
        """Arithmetic operation for *.

        Multiplies the I, O, and eut attributes of this Recipe.
        Only runnable once.
        """
        assert self.multiplier == -1, 'Cannot multiply recipe multiple times'

        self.I *= mul_num
        self.O *= mul_num
        self.eut *= mul_num
        self.multiplier = mul_num

        return self
