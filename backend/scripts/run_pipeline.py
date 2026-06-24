"""CLI to run the full pipeline once and print a summary.

Usage (from backend/):
    python -m scripts.run_pipeline                 # uses TARGET_ZIP
    python -m scripts.run_pipeline --zip 10013 --radius 25 --reenrich
"""
from __future__ import annotations

import argparse

from app.config import get_settings
from app.db import init_db
from app.pipeline.orchestrator import PipelineOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Cosailor lead pipeline.")
    parser.add_argument("--zip", dest="zip_code", default=None)
    parser.add_argument("--radius", dest="radius", type=int, default=None)
    parser.add_argument("--reenrich", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    init_db()

    print(
        f"Running pipeline (zip={args.zip_code or settings.target_zip}, "
        f"mock_mode={settings.effective_mock_mode})..."
    )
    result = PipelineOrchestrator(settings).run_sync(
        zip_code=args.zip_code, radius=args.radius, reenrich=args.reenrich
    )
    print(
        f"\nRun #{result.run_id} complete:\n"
        f"  discovered: {result.discovered}\n"
        f"  new:        {result.new}\n"
        f"  enriched:   {result.enriched}\n"
        f"  failed:     {result.failed}"
    )
    if result.errors:
        print("  errors:")
        for err in result.errors[:5]:
            print(f"    - {err}")


if __name__ == "__main__":
    main()
