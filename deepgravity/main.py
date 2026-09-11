"""Entry point: python -m deepgravity.main --config PATH."""
import argparse
import json
from pathlib import Path

from .runner import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True,
                        help="JSON configuration; relative paths resolve from its directory")
    args = parser.parse_args()
    path = args.config.resolve()
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    output, summary = run(config, path.parent)
    print(json.dumps({"run_directory": str(output), "metrics": summary}, indent=2))


if __name__ == "__main__":
    main()
