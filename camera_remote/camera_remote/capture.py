from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional

from .config import load_config
from .storage import SnapshotStorage


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/camera-remote/config.ini")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--blocking", action="store_true")
    args = parser.parse_args(argv)

    configure_logging()
    config = load_config(args.config)
    storage = SnapshotStorage(config)
    result = storage.capture_once(blocking=args.blocking)
    if result.skipped:
        logging.info("snapshot skipped: %s", result.message)
        return 0
    logging.info("snapshot written: %s", result.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
