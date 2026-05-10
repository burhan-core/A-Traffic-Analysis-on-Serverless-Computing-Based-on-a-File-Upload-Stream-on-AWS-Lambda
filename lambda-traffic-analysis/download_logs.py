"""
download_logs.py
Downloads Lambda REPORT logs from AWS CloudWatch and saves as CSV.

EDIT:
    REGION      — your AWS region (e.g. "ap-south-1" for Mumbai)
    HOURS_BACK  — how many hours of logs to pull
    FUNCTIONS   — list of Lambda function names to download logs for

RUN:
    python download_logs.py
"""

import boto3
import csv
import time
import json
from datetime import datetime, timedelta, timezone

# ─── CHANGE THESE ─────────────────────────────────────────────────────────────
REGION     = "ap-south-1"     
HOURS_BACK = 200
OUTPUT_CSV = "cloudwatch_logs.csv"

FUNCTIONS = [
    "traffic-analysis-128mb",
    "traffic-analysis-512mb",
    "traffic-analysis-3008mb",
]
# ──────────────────────────────────────────────────────────────────────────────

client = boto3.client("logs", region_name=REGION)


def query_log_group(log_group: str, hours_back: int) -> list[dict]:
    """Run a CloudWatch Insights query and return results as list of dicts."""
    end_time   = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time = int((datetime.now(timezone.utc) - timedelta(hours=hours_back)).timestamp() * 1000)

    query_string = """
        fields @timestamp, @requestId, @duration, @billedDuration,
               @memorySize, @maxMemoryUsed, @initDuration, @logStream
        | filter @type = "REPORT"
        | sort @timestamp asc
        | limit 10000
    """

    print(f"  Querying {log_group} ...")
    try:
        response = client.start_query(
            logGroupName=log_group,
            startTime=start_time,
            endTime=end_time,
            queryString=query_string,
        )
        query_id = response["queryId"]
    except client.exceptions.ResourceNotFoundException:
        print(f"  [WARN] Log group {log_group} not found -- skipping.")
        return []

    # Poll until complete
    while True:
        result = client.get_query_results(queryId=query_id)
        status = result["status"]
        if status == "Complete":
            break
        if status in ("Failed", "Cancelled"):
            print(f"  [FAIL] Query {status} for {log_group}")
            return []
        print(f"  Waiting... ({status})")
        time.sleep(2)

    rows = []
    for record in result["results"]:
        row = {field["field"]: field["value"] for field in record}
        row["log_group"] = log_group
        rows.append(row)

    print(f"  [OK] {len(rows)} REPORT entries")
    return rows


def main():
    all_rows = []
    for fn in FUNCTIONS:
        log_group = f"/aws/lambda/{fn}"
        rows = query_log_group(log_group, HOURS_BACK)
        all_rows.extend(rows)

    if not all_rows:
        print("No data found. Make sure your functions have been invoked.")
        return

    # Write CSV
    fieldnames = [
        "log_group", "@timestamp", "@requestId", "@duration",
        "@billedDuration", "@memorySize", "@maxMemoryUsed",
        "@initDuration", "@logStream",
    ]
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n[OK] Saved {len(all_rows)} rows -> {OUTPUT_CSV}")

    # Quick summary
    cold = [r for r in all_rows if r.get("@initDuration")]
    print(f"\nQuick stats:")
    print(f"  Total REPORT entries : {len(all_rows)}")
    print(f"  Cold starts          : {len(cold)}")
    durations = [float(r["@duration"]) for r in all_rows if r.get("@duration")]
    if durations:
        print(f"  Avg duration         : {sum(durations)/len(durations):.1f} ms")
        print(f"  Min / Max duration   : {min(durations):.1f} / {max(durations):.1f} ms")


if __name__ == "__main__":
    main()
