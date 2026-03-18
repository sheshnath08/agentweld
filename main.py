# Development convenience shim — not part of the installed package.
# The installed CLI entry point is: agentforge.cli.main:app
# Install with: pip install -e .[dev]
# Then run: agentforge --help

from agentforge.cli.main import app

if __name__ == "__main__":
    app()
