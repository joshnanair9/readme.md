import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from pipeline_monitor import analyse_runs, load_runs, render_markdown


class PipelineMonitorTests(unittest.TestCase):
    def make_run(self, status="Succeeded", start="2026-10-13T08:00:00Z",
                 end="2026-10-13T08:10:00Z", rows=10, error=""):
        from pipeline_monitor import parse_timestamp
        return {
            "pipeline_name": "example_pipeline",
            "run_id": "run-1",
            "status": status,
            "status_normalized": status.casefold(),
            "start_time": parse_timestamp(start, field="start_time", run_id="run-1"),
            "end_time": parse_timestamp(end, field="end_time", run_id="run-1"),
            "rows_processed": rows,
            "error_message": error,
        }

    def test_summary_counts_and_success_rate(self):
        runs = [
            self.make_run("Succeeded", rows=10),
            self.make_run("Failed", rows=0, error="sample failure"),
            self.make_run("Running", end="", rows=5),
        ]
        now = datetime(2026, 10, 13, 9, 30, tzinfo=timezone.utc)
        report = analyse_runs(runs, now=now, long_running_minutes=60)
        self.assertEqual(report["summary"]["total_runs"], 3)
        self.assertEqual(report["summary"]["succeeded"], 1)
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertEqual(report["summary"]["running"], 1)
        self.assertEqual(report["summary"]["completed_success_rate_percent"], 50.0)
        self.assertEqual(report["summary"]["total_rows_processed"], 15)
        self.assertEqual(len(report["failures"]), 1)
        self.assertEqual(len(report["long_running"]), 1)

    def test_empty_report_has_no_success_rate(self):
        report = analyse_runs([], now=datetime(2026, 10, 13, tzinfo=timezone.utc))
        self.assertIsNone(report["summary"]["completed_success_rate_percent"])

    def test_markdown_contains_failure(self):
        report = analyse_runs(
            [self.make_run("Failed", error="sample failure")],
            now=datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc),
        )
        markdown = render_markdown(report)
        self.assertIn("Failed runs", markdown)
        self.assertIn("sample failure", markdown)

    def test_load_csv_and_reject_negative_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.csv"
            columns = [
                "pipeline_name", "run_id", "status", "start_time",
                "end_time", "rows_processed", "error_message",
            ]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerow({
                    "pipeline_name": "example", "run_id": "run-2",
                    "status": "Succeeded", "start_time": "2026-10-13T08:00:00Z",
                    "end_time": "2026-10-13T08:10:00Z", "rows_processed": "-1",
                    "error_message": "",
                })
            with self.assertRaisesRegex(ValueError, "negative"):
                load_runs(path)


if __name__ == "__main__":
    unittest.main()
