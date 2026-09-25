"""MUSA MCP server (M1.6): operate a museum's collection from any MCP client.

Three roles at once (docs/M1_plano.md): development ergonomics, the base of the
AI assistant, and an operations channel. Every answer that states something
about the collection cites its sources (card paths and asset_ids) — the rule
from docs/Musa_design implementacao-usd.md §7.

Run against a client repository:

    python -m mcp_server --repo ../DemoMuseum

Zero dependencies beyond the builder package: the stdio JSON-RPC loop is
implemented here (mcp_server/server.py) so the tool travels with the repo.
"""

__version__ = "0.1.0"
