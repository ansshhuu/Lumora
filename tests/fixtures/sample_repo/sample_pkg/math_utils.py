"""Small arithmetic helpers with no third-party dependencies."""

import math


def add(a: float, b: float) -> float:
    """Return the sum of two numbers."""
    return a + b


def divide(numerator: float, denominator: float) -> float:
    """Divide two numbers, raising on a zero denominator."""
    if denominator == 0:
        raise ZeroDivisionError("denominator must be non-zero")
    return numerator / denominator


def mean(values):
    # Deliberately undocumented: the parser must report docstring=None here.
    if not values:
        return 0.0
    return sum(values) / len(values)


class Accumulator:
    """Running total that can be reset."""

    def __init__(self, start: float = 0.0) -> None:
        self.total = start

    def push(self, value: float) -> float:
        """Add a value to the running total and return the new total."""
        self.total = add(self.total, value)
        return self.total

    def reset(self) -> None:
        """Clear the running total."""
        self.total = 0.0

    @property
    def magnitude(self) -> float:
        """Absolute value of the current total."""
        return math.fabs(self.total)
