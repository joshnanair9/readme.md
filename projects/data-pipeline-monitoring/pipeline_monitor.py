#!/usr/bin/env python3
"""Summarise data pipeline run records from a CSV file.

Uses only the Python standard library and is designed for local portfolio demos.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = {
    "pipeline_name",
    "run_id",
    "status",
    "start_time",
    "end_time",
    "rows_processed",
    "error_message",
}
SUCCESS_STATUSES = {"succeeded", "success", "completed"}
FAILURE_STATUSES = {"failed", "failure", "error"}
RUNNING_STATUSES = {"running", "in progress", "in_progress"}


def parse_timestamp(value: str, *, field: str, run_id: str) -> datetime | None:
    """Parse an ISO-8601 timestamp; blank values return None."""
    value = value.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"Run {run_id!r} has an invalid {field}: {value!r}. "
            "Use an ISO-8601 timestamp."
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_runs(csv_path: Path) -> list[dict[str, Any]]:
    """Load and validate run records from CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {csv_path}")

    runs: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(
                "CSV is missing required column(s): " + ", ".join(sorted(missing))
            )

        for line_number, row in enumerate(reader, start=2):
            run_id = (row.get("run_id") or "").strip() or f"line-{line_number}"
            pipeline_name = (row.get("pipeline_name") or "").strip()
            status = (row.get("status") or "").strip()
            if not pipeline_name:
                raise ValueError(f"Line {line_number}: pipeline_name cannot be blank.")
            if not status:
                raise ValueError(f"Line {line_number}: status cannot be blank.")

            raw_rows = (row.get("rows_processed") or "").strip()
            try:
                rows_processed = int(raw_rows or "0")
            except ValueError as exc:
                raise ValueError(
                    f"Run {run_id!r} has an invalid rows_processed value: {raw_rows!r}."
                ) from exc
            if rows_processed < 0:
                raise ValueError(
                    f"Run {run_id!r} has a negative rows_processed value."
                )

            start = parse_timestamp(
                row.get("start_time") or "", field="start_time", run_id=run_id
            )
            end = parse_timestamp(
                row.get("end_time") or "", field="end_time", run_id=run_id
            )
            if start is None:
                raise ValueError(f"Run {run_id!r} is missing start_time.")
            if end is not None and end < start:
                raise ValueError(
                    f"Run {run_id!r} ends before it starts."
                )

            runs.append({
                "pipeline_name": pipeline_name,
                "run_id": run_id,
                "status": status,
                "status_normalized": status.casefold(),
                "start_time": start,
                "end_time": end,
                "rows_processed": rows_processed,
                "error_message": (row.get("error_message") or "").strip(),
            })
    return runs


def analyse_runs(
    runs: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    long_running_minutes: float = 60,
) -> dict[str, Any]:
    """Create summary metrics and per-run findings."""
    if long_running_minutes < 0:
        raise ValueError("long_running_minutes must be zero or greater.")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    counts: Counter[str] = Counter()
    total_rows = 0
    failures: list[dict[str, Any]] = []
    long_running: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    for run in runs:
        status = run["status_normalized"]
        if status in SUCCESS_STATUSES:
            category = "succeeded"
        elif status in FAILURE_STATUSES:
            category = "failed"
        elif status in RUNNING_STATUSES:
            category = "running"
        else:
            category = "other"
        counts[category] += 1
        total_rows += run["rows_processed"]

        finish = run["end_time"] or current
        duration_minutes = max(
            0.0, (finish - run["start_time"]).total_seconds() / 60
        )
        detail = {
            "pipeline_name": run["pipeline_name"],
            "run_id": run["run_id"],
            "status": run["status"],
            "category": category,
            "duration_minutes": round(duration_minutes, 2),
            "rows_processed": run["rows_processed"],
            "error_message": run["error_message"],
        }
        details.append(detail)

        if category == "failed":
            failures.append(detail)
        if category == "running" and duration_minutes >= long_running_minutes:
            long_running.append(detail)

    total = len(runs)
    completed = counts["succeeded"] + counts["failed"]
    success_rate = round(counts["succeeded"] / completed * 100, 2) if completed else None

    return {
        "generated_at": current.isoformat(),
        "threshold_minutes": long_running_minutes,
        "summary": {
            "total_runs": total,
            "succeeded": counts["succeeded"],
            "failed": counts["failed"],
            "running": counts["running"],
            "other": counts["other"],
            "completed_success_rate_percent": success_rate,
            "total_rows_processed": total_rows,
        },
        "failures": failures,
        "long_running": long_running,
        "runs": details,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render report as Markdown."""
    summary = report["summary"]
    success_rate = summary["completed_success_rate_percent"]
    rate_text = f"{success_rate}%" if success_rate is not None else "N/A"
    lines = [
        "# Data Pipeline Monitoring Report",
        "",
        f"- Generated at (UTC): {report['generated_at']}",
        f"- Long-running threshold: {report['threshold_minutes']} minutes",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total runs | {summary['total_runs']} |",
        f"| Succeeded | {summary['succeeded']} |",
        f"| Failed | {summary['failed']} |",
        f"| Running | {summary['running']} |",
        f"| Other statuses | {summary['other']} |",
        f"| Completed success rate | {rate_text} |",
        f"| Rows processed | {summary['total_rows_processed']:,} |",
        "",
        "## Failed runs",
        "",
    ]
    if report["failures"]:
        lines.extend([
            "| Pipeline | Run ID | Error |",
            "|---|---|---|",
        ])
        for item in report["failures"]:
            error = item["error_message"].replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {item['pipeline_name']} | {item['run_id']} | {error or 'No error message supplied'} |"
            )
    else:
        lines.append("No failed runs found.")

    lines.extend(["", "## Long-running jobs", ""])
    if report["long_running"]:
        lines.extend([
            "| Pipeline | Run ID | Duration (minutes) |",
            "|---|---|---:|",
        ])
        for item in report["long_running"]:
            lines.append(
                f"| {item['pipeline_name']} | {item['run_id']} | {item['duration_minutes']:.2f} |"
            )
    else:
        lines.append("No running jobs exceeded the configured threshold.")

    lines.extend(["", "---", "_Generated by the Data Pipeline Monitoring Toolkit._", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyse CSV pipeline run records and generate operational reports."
    )
    parser.add_argument("--input", type=Path, required=True, help="Path to the run-history CSV.")
    parser.add_argument("--markdown", type=Path, help="Optional Markdown report output path.")
    parser.add_argument("--json", dest="json_path", type=Path, help="Optional JSON report output path.")
    parser.add_argument(
        "--long-running-minutes", type=float, default=60,
        help="Flag running jobs at or above this duration (default: 60).",
    )
    args = parser.parse_args(argv)

    try:
        runs = load_runs(args.input)
        report = analyse_runs(runs, long_running_minutes=args.long_running_minutes)
        markdown = render_markdown(report)
        if args.markdown:
            args.markdown.write_text(markdown + "\n", encoding="utf-8")
        if args.json_path:
            args.json_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if not args.markdown and not args.json_path:
            print(markdown)
        return 1 if report["summary"]["failed"] else 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
