"""Command line interface: ``python -m musa_build build|validate``."""

import argparse
import sys
from pathlib import Path

from .build import BuildFailure, build_site
from .report import BuildReport


def _cmd_build(args) -> int:
    out = Path(args.out)
    try:
        report = build_site(repo=Path(args.repo), frontend=Path(args.frontend), out=out)
    except BuildFailure as failure:
        out.mkdir(parents=True, exist_ok=True)
        failure.report.write(out)
        print(f"BUILD FAILED — {len(failure.report.errors)} error(s); see {out / 'build-report.md'}")
        for error in failure.report.errors:
            print(f"  ERROR {error}")
        return 1
    counts = report.counts()
    print(
        f"BUILD OK — {counts['items_included']} item(s) published, "
        f"{counts['items_excluded']} excluded; site at {out}"
    )
    print(f"report: {out / 'build-report.md'}")
    return 0


def _cmd_validate(args) -> int:
    """Validate and gate without emitting a site (dry run)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        # validate = build into a throwaway dir with the real frontend replaced by nothing:
        # contract errors and gate decisions are exactly the build's.
        code = _cmd_build(argparse.Namespace(repo=args.repo, frontend=args.frontend, out=tmp))
        if code == 0:
            print("validate: contract OK, gating decisions in the build report above")
        return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="musa-build",
        description="Build a MUSA client repository (museum.config.json + content/) into the museum's static site.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="validate, gate and emit the static site")
    build.add_argument("--repo", required=True, help="client repository root (museum.config.json + content/)")
    build.add_argument("--frontend", required=True, help="platform frontend directory (bundled in the artifact image)")
    build.add_argument("--out", required=True, help="output directory for the static site")
    build.set_defaults(func=_cmd_build)

    validate = commands.add_parser("validate", help="validate and report without keeping the emitted site")
    validate.add_argument("--repo", required=True)
    validate.add_argument("--frontend", required=True)
    validate.set_defaults(func=_cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
