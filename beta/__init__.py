"""M3 — virtual client: synthetic personas, misuse generator, invariants.

The personas drive the product exactly like a real curator: HTTP against
`musa-build serve` (ADR 0014). Persona actions never call builder internals;
only the verification code (invariants.py) may import the platform contract
validator. See docs/M3_plano.md.
"""

import sys
from pathlib import Path

# The beta tooling is platform code: it boots `musa-build serve` and uses the
# platform contract validator for verification. Make the builder importable
# regardless of the caller's cwd.
_BUILDER = Path(__file__).resolve().parent.parent / "builder"
if str(_BUILDER) not in sys.path:
    sys.path.insert(0, str(_BUILDER))
