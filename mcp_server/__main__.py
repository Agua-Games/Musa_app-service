"""Entry point: ``python -m mcp_server --repo <client-repository>``."""

import argparse
import sys
from pathlib import Path

from . import __version__
from . import tools as toolbox_module
from .server import make_handler, serve


class Toolbox:
    """Binds the collection tools to one client repository."""

    def __init__(self, repo: Path):
        self.repo = toolbox_module.MusaRepo(repo)
        self.version = __version__
        self.tools = {
            "list_collections": lambda **kw: toolbox_module.list_collections(self.repo),
            "get_item": lambda **kw: toolbox_module.get_item(self.repo, **kw),
            "search": lambda **kw: toolbox_module.search(self.repo, **kw),
            "validate_card": lambda **kw: toolbox_module.validate_card_tool(self.repo, **kw),
            "propose_card_correction": lambda **kw: toolbox_module.propose_card_correction(self.repo, **kw),
            "upload_asset": lambda **kw: toolbox_module.upload_asset(self.repo, **kw),
            "set_status": lambda **kw: toolbox_module.set_status(self.repo, **kw),
            "build_report": lambda **kw: toolbox_module.build_report(self.repo),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="musa-mcp",
        description="MUSA MCP server — operate a museum's collection over MCP (stdio).",
    )
    parser.add_argument("--repo", required=True, help="client repository root (museum.config.json + content/)")
    args = parser.parse_args(argv)

    try:
        toolbox = Toolbox(Path(args.repo))
    except ValueError as exc:
        print(f"musa-mcp: {exc}", file=sys.stderr)
        return 1

    # Protocol goes to stdout; anything human-facing goes to stderr.
    print(f"musa-mcp {__version__} serving {toolbox.repo.repo}", file=sys.stderr)
    serve(make_handler(toolbox))
    return 0


if __name__ == "__main__":
    sys.exit(main())
