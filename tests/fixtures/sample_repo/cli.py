"""Command line entry point for the sample package."""

import sys

from sample_pkg.math_utils import Accumulator
from sample_pkg.store import Store


def build_store() -> Store:
    """Create an empty store; kept separate so tests can stub it."""
    return Store()


def main(argv=None) -> int:
    """Run the demo pipeline and return a process exit code."""
    argv = argv if argv is not None else sys.argv[1:]
    acc = Accumulator()
    for arg in argv:
        acc.push(float(arg))
    print(acc.total)
    return 0
