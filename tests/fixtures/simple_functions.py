"""Fixture: top-level functions with and without docstrings."""


def greet(name):
    """Return a greeting for the given name."""
    return f"Hello, {name}"


def add(a, b):
    return a + b


def outer():
    """Outer function containing a nested helper."""

    def inner():
        return 1

    return inner()
