"""Fixture: classes, methods, and nesting for qualified-name tests."""


class Calculator:
    """A small calculator."""

    def add(self, a, b):
        """Add two numbers."""
        return a + b

    def subtract(self, a, b):
        return a - b


class Outer:
    class Inner:
        """A nested class."""

        def deep_method(self):
            return "deep"


def standalone():
    return None
