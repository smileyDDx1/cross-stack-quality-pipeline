"""Turns Locust's --csv stats file into a Markdown table (used for the GitHub Actions job summary)."""

import csv
import sys


def main(path: str) -> None:
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    print("### Load test results\n")
    print("| Endpoint | Requests | Failures | Median (ms) | p95 (ms) | p99 (ms) | Req/s |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        if row["Name"].startswith("[") or not row["Request Count"]:
            continue
        # Request names already start with the HTTP method (see locustfile.py).
        name = "**Total**" if row["Name"] == "Aggregated" else f"`{row['Name']}`"
        print(
            f"| {name} | {row['Request Count']} | {row['Failure Count']} | {row['50%']} | {row['95%']} "
            f"| {row['99%']} | {float(row['Requests/s']):.1f} |"
        )


if __name__ == "__main__":
    main(sys.argv[1])
