# Data Pipeline Monitoring Toolkit

A lightweight Python CLI that analyses pipeline run records from a CSV file and produces a readable operational summary in Markdown and JSON.

This portfolio project demonstrates practical monitoring patterns for data engineering teams without connecting to any production environment.

## Features

- Summarises total, successful, failed, running, and unknown-status runs
- Calculates success rate and total processed rows
- Highlights failed runs and their error messages
- Flags long-running jobs using a configurable threshold
- Writes Markdown and JSON reports
- Uses only the Python standard library
- Includes synthetic sample data and unit tests

## Requirements

- Python 3.10 or newer
- No third-party packages required

## Quick start

From this directory, run:

```bash
python pipeline_monitor.py --input sample_runs.csv --markdown report.md --json report.json
```

Flag long-running jobs that exceed 45 minutes:

```bash
python pipeline_monitor.py --input sample_runs.csv --long-running-minutes 45
```

Use your own CSV file with these required columns:

| Column | Description |
|---|---|
| `pipeline_name` | Name of the pipeline |
| `run_id` | Unique identifier for the run |
| `status` | Succeeded, Failed, Running, or another status |
| `start_time` | ISO-8601 timestamp, e.g. `2026-10-13T09:00:00+00:00` |
| `end_time` | ISO-8601 timestamp; blank for a running job |
| `rows_processed` | Number of rows processed; use 0 if unknown |
| `error_message` | Error details, if any |

Timestamps without a UTC offset are treated as UTC. Running jobs are measured from their start time to the current time.

## Example output

For the included synthetic data, the report summarises completed successes and failures, calls out the failed pipeline runs, and lists jobs that exceed the configured duration threshold.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Design notes

- Input data is validated, and malformed timestamps or row counts produce actionable errors.
- Status matching is case-insensitive.
- Reports are intended for demonstration and local analysis, not as a replacement for production observability or alerting.
- All included run records are fictional sample data.

## Possible extensions

- Azure Data Factory or Synapse monitoring API adapter
- Snowflake task history adapter
- Email or Teams notifications
- Trend reports and historical storage
- Configurable service-level thresholds

## Repository structure

```text
data-pipeline-monitoring/
├── README.md
├── pipeline_monitor.py
├── sample_runs.csv
└── tests/
    └── test_pipeline_monitor.py
```
