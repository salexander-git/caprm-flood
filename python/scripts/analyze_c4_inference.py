"""C4 item 1, analysed. Which measured differences survive their own spread.

    python python/scripts/analyze_c4_inference.py `
        --runs outputs/validation/c4_inference_benchmark_threads1.json `
               outputs/validation/c4_inference_benchmark_threads8.json

Reads only the run artifacts and modifies none of them. Thread counts are read
from each run's recorded environment rather than supplied on the command line,
so a run that failed to pin its threads is rejected instead of mislabelled.

Writes
    outputs/validation/c4_inference_analysis.json
    docs/c4_inference_tables.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPOSITORY_ROOT / "python"))

from caprm import c4_analysis as c4a  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolution-test the C4 inference sweep across batch size and thread count."
    )
    parser.add_argument(
        "--runs",
        nargs=2,
        required=True,
        help="Two c4_inference_v1 artifacts at different pinned thread counts.",
    )
    parser.add_argument("--output", default="outputs/validation/c4_inference_analysis.json")
    parser.add_argument("--markdown", default="docs/c4_inference_tables.md")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    runs: dict[int, dict] = {}
    for token in args.runs:
        path = REPOSITORY_ROOT / token
        run = c4a.load_run(path)
        threads = c4a.thread_count(run)
        if threads in runs:
            raise SystemExit(f"two runs both pinned at {threads} threads; nothing to compare")
        runs[threads] = run

    analysis = c4a.analyse(runs)
    analysis["generated_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    analysis["inputs"] = {
        token: c4a.thread_count(c4a.load_run(REPOSITORY_ROOT / token)) for token in args.runs
    }

    output_path = REPOSITORY_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(analysis, indent=2, default=float), encoding="utf-8")

    markdown_path = REPOSITORY_ROOT / args.markdown
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = c4a.markdown_tables(analysis)
    markdown_path.write_text(markdown, encoding="utf-8")

    print(markdown)
    print(f"wrote {output_path}")
    print(f"wrote {markdown_path}")

    breaching = analysis["agreement"]["per_thread_count"]
    for threads, entry in sorted(breaching.items()):
        if entry["breaching_batches"]:
            print(
                f"  agreement: at {threads} threads, batches "
                f"{entry['breaching_batches']} exceed {entry['tolerance_index_points']:.3e}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())