# Development convenience shim — not part of the installed package.
# The installed CLI entry point is: agentweld.cli.main:app
# Install with: pip install -e .[dev]
# Then run: agentweld --help

from agentweld.cli.main import app

if __name__ == "__main__":
    app()
