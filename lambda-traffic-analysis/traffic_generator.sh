#!/bin/bash
# =============================================================================
# traffic_generator.sh
# Replicates the 6-interval traffic pattern from Muller et al. 2020
#
# EDIT THESE BEFORE RUNNING:
#   API_128, API_512, API_3008  — paste the URLs from "sam deploy" output
#
# USAGE:
#   chmod +x traffic_generator.sh
#   ./traffic_generator.sh          # runs all 6 intervals (~24 h total)
#   ./traffic_generator.sh 1        # run only interval 1
#   ./traffic_generator.sh 1 3      # run intervals 1 through 3
# =============================================================================

# ─── CHANGE THESE ────────────────────────────────────────────────────────────
API_128="https://pqwqw91vyd.execute-api.ap-south-1.amazonaws.com/Prod/upload128"
API_512="https://pqwqw91vyd.execute-api.ap-south-1.amazonaws.com/Prod/upload512"
API_3008="https://pqwqw91vyd.execute-api.ap-south-1.amazonaws.com/Prod/upload3008"
# ─────────────────────────────────────────────────────────────────────────────

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/traffic_log_${TIMESTAMP}.csv"

echo "timestamp,interval,request_id,memory_mb,http_status,rtt_ms,body" > "$LOG_FILE"
echo "Logging to: $LOG_FILE"

# ── helper: send one POST request ────────────────────────────────────────────
send_request() {
    local interval="$1"
    local memory_mb="$2"
    local req_id="$3"
    local url

    case "$memory_mb" in
        128)  url="$API_128" ;;
        512)  url="$API_512" ;;
        3008) url="$API_3008" ;;
        *)    url="$API_128" ;;
    esac

    local ts; ts=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
    local payload="interval=${interval} reqId=${req_id} ts=${ts}"

    local start_ns; start_ns=$(date +%s%N 2>/dev/null || python3 -c "import time; print(int(time.time()*1e9))")

    local response
    response=$(curl -s -w "\n%{http_code}" \
        -X POST "$url" \
        -H "Content-Type: text/plain" \
        --data "$payload" \
        --max-time 45 2>/dev/null)

    local http_code; http_code=$(echo "$response" | tail -1)
    local body;      body=$(echo "$response" | head -n -1 | tr ',' ';' | tr '\n' ' ')

    local end_ns; end_ns=$(date +%s%N 2>/dev/null || python3 -c "import time; print(int(time.time()*1e9))")
    local rtt_ms=$(( (end_ns - start_ns) / 1000000 ))

    echo "$ts,$interval,$req_id,$memory_mb,$http_code,$rtt_ms,\"$body\"" >> "$LOG_FILE"
    printf "  [%s] req=%-6s mem=%-4sMB  HTTP=%s  RTT=%sms\n" \
           "$interval" "$req_id" "$memory_mb" "$http_code" "$rtt_ms"
}

# ── interval runner ───────────────────────────────────────────────────────────
run_interval() {
    local interval="$1"
    local concurrency="$2"
    local count="$3"
    local min_sleep="$4"
    local max_sleep="$5"
    local memory="$6"

    echo ""
    echo "=== $interval | concurrency=$concurrency | requests=$count | sleep=${min_sleep}-${max_sleep}s | mem=${memory}MB ==="

    for i in $(seq 1 "$count"); do
        for c in $(seq 1 "$concurrency"); do
            send_request "$interval" "$memory" "${i}_${c}" &
        done
        wait

        if [ "$max_sleep" -gt 0 ]; then
            local sleep_time=$(( RANDOM % (max_sleep - min_sleep + 1) + min_sleep ))
            echo "  sleeping ${sleep_time}s..."
            sleep "$sleep_time"
        fi
    done
}

START_INTERVAL="${1:-1}"
END_INTERVAL="${2:-6}"

echo "Running intervals $START_INTERVAL to $END_INTERVAL"
echo "Start time: $(date)"

# Interval 1 — 1 req, 1–5 min gap, 5 h → warm instance study
[ "$START_INTERVAL" -le 1 ] && [ "$END_INTERVAL" -ge 1 ] && \
    run_interval "interval1_single_1to5min" 1 50 60 300 128

# Interval 2 — 1 req, 0–4 min gap
[ "$START_INTERVAL" -le 2 ] && [ "$END_INTERVAL" -ge 2 ] && \
    run_interval "interval2_single_0to4min" 1 54 0 240 128

# Interval 3 — 2 concurrent, 0–3 min gap
[ "$START_INTERVAL" -le 3 ] && [ "$END_INTERVAL" -ge 3 ] && \
    run_interval "interval3_dual_0to3min" 2 50 0 180 128

# Interval 4 — 4 concurrent, 0–3 min gap (stress test)
[ "$START_INTERVAL" -le 4 ] && [ "$END_INTERVAL" -ge 4 ] && \
    run_interval "interval4_quad_0to3min" 4 50 0 180 128

# Interval 5 — 2 concurrent, tight 0–2 min gap
[ "$START_INTERVAL" -le 5 ] && [ "$END_INTERVAL" -ge 5 ] && \
    run_interval "interval5_dual_0to2min" 2 50 0 120 128

# Interval 6 — 2 concurrent, long 0–10 min gap (cold-start trigger)
[ "$START_INTERVAL" -le 6 ] && [ "$END_INTERVAL" -ge 6 ] && \
    run_interval "interval6_dual_0to10min" 2 30 0 600 128

echo ""
echo "Done! Log file: $LOG_FILE"
echo "End time: $(date)"
