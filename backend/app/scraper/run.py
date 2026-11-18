"""CLI entry point: `python -m app.scraper.run --source both --limit 40`."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.config import get_settings
from app.scraper.darglobal import DarGlobalScraper
from app.scraper.wasalt import WasaltScraper

settings = get_settings()


async def main(source: str, limit: int, output: Path) -> None:
    report: dict[str, object] = {}
    if source in ("both", "darglobal"):
        async with DarGlobalScraper(output) as scraper:
            report["darglobal"] = {"records": len(await scraper.run(limit))}
    if source in ("both", "wasalt"):
        async with WasaltScraper(output) as scraper:
            records, note = await scraper.run(limit)
            report["wasalt"] = {"records": len(records), "blocking_note": note}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polite public-data acquisition")
    parser.add_argument("--source", choices=["both", "darglobal", "wasalt"], default="both")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    asyncio.run(main(args.source, args.limit, args.output))
