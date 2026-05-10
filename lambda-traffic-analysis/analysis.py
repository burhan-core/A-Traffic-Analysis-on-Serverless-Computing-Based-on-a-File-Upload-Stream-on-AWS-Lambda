"""
analysis.py
Replicates the statistical analysis and plots from Muller et al. 2020.

RUN:
    pip install pandas matplotlib scipy numpy
    python analysis.py

INPUT FILES (both must exist in the same folder):
    cloudwatch_logs.csv   — from download_logs.py
    logs/traffic_log_*.csv — from traffic_generator.sh  (auto-detected)
"""

import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats

# ── output folder ─────────────────────────────────────────────────────────────
os.makedirs("plots", exist_ok=True)

# ═════════════════════════════════════════════════════════════════════════════
# 1. LOAD DATA
# ═════════════════════════════════════════════════════════════════════════════

# CloudWatch REPORT logs
cw_file = "cloudwatch_logs.csv"
if not os.path.exists(cw_file):
    print(f"Missing {cw_file} -- run download_logs.py first.")
    exit(1)

cw = pd.read_csv(cw_file)
for col in ["@duration", "@billedDuration", "@maxMemoryUsed", "@initDuration", "@memorySize"]:
    cw[col] = pd.to_numeric(cw[col], errors="coerce")
cw["@timestamp"] = pd.to_datetime(cw["@timestamp"], errors="coerce")

# CloudWatch may return memorySize/maxMemoryUsed in bytes — convert to MB if needed
if cw["@memorySize"].median() > 10000:
    cw["@memorySize"] = cw["@memorySize"] / 1_000_000
    cw["@maxMemoryUsed"] = cw["@maxMemoryUsed"] / 1_000_000

# Traffic generator logs (latest file auto-detected)
traffic_files = sorted(glob.glob("logs/traffic_log_*.csv"))
traffic = None
if traffic_files:
    traffic = pd.read_csv(traffic_files[-1], parse_dates=["timestamp"])
    traffic["rtt_ms"] = pd.to_numeric(traffic["rtt_ms"], errors="coerce")
    print(f"Loaded traffic log: {traffic_files[-1]}")
else:
    print("No traffic log found -- skipping RTT plots.")

cold  = cw[cw["@initDuration"].notna()].copy()
warm  = cw[cw["@initDuration"].isna()].copy()

# ═════════════════════════════════════════════════════════════════════════════
# 2. DESCRIPTIVE STATISTICS
# ═════════════════════════════════════════════════════════════════════════════

print("\n" + "="*55)
print("COLD-START STATISTICS")
print("="*55)
print(f"  Total requests        : {len(cw)}")
print(f"  Cold starts           : {len(cold)}  ({100*len(cold)/len(cw):.1f}%)")
print(f"  Warm starts           : {len(warm)}")

if len(cold) > 0:
    print(f"\n  initDuration (ms)")
    print(f"    Median  : {cold['@initDuration'].median():.1f}")
    print(f"    Mean    : {cold['@initDuration'].mean():.1f}")
    print(f"    Std dev : {cold['@initDuration'].std():.1f}")
    print(f"    Min     : {cold['@initDuration'].min():.1f}")
    print(f"    Max     : {cold['@initDuration'].max():.1f}")

    pct = cold["@initDuration"].median() / cold["@duration"].median() * 100
    print(f"\n  Cold-Start as % of exec duration (median): {pct:.1f}%")

print(f"\n  Execution Duration (all requests, ms)")
print(f"    Mean    : {cw['@duration'].mean():.1f}")
print(f"    Median  : {cw['@duration'].median():.1f}")
print(f"    Std dev : {cw['@duration'].std():.1f}")

print(f"\n  Memory used (avg): {cw['@maxMemoryUsed'].mean():.1f} MB")

# Memory size breakdown
if "@memorySize" in cw.columns:
    print("\n  Duration by memory config:")
    for mem, grp in cw.groupby("@memorySize"):
        print(f"    {int(mem):>5} MB -> mean={grp['@duration'].mean():.1f}ms  "
              f"cold_pct={100*grp['@initDuration'].notna().sum()/len(grp):.1f}%")

# ═════════════════════════════════════════════════════════════════════════════
# 3. PLOT 1 — Cold-Start Distribution (boxplot + histogram)
# ═════════════════════════════════════════════════════════════════════════════

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Figure 1 — Cold-Start Analysis", fontsize=14, fontweight="bold")

# Boxplot: cold vs warm execution duration
bp_data = []
bp_labels = []
if len(cold) > 0:
    bp_data.append(cold["@duration"].dropna())
    bp_labels.append(f"Cold start\n(n={len(cold)})")
if len(warm) > 0:
    bp_data.append(warm["@duration"].dropna())
    bp_labels.append(f"Warm start\n(n={len(warm)})")

if bp_data:
    axes[0].boxplot(bp_data, tick_labels=bp_labels, patch_artist=True,
                    boxprops=dict(facecolor="#B5D4F4", color="#185FA5"),
                    medianprops=dict(color="#E24B4A", linewidth=2))
    axes[0].set_ylabel("Execution Duration (ms)")
    axes[0].set_title("Cold vs Warm Execution Duration")
    axes[0].grid(axis="y", alpha=0.4)

# Histogram: initDuration
if len(cold) > 0:
    axes[1].hist(cold["@initDuration"].dropna(), bins=25,
                 color="#E8593C", alpha=0.8, edgecolor="white")
    axes[1].axvline(cold["@initDuration"].median(), color="#042C53",
                    linestyle="--", linewidth=1.8, label=f"Median = {cold['@initDuration'].median():.0f} ms")
    axes[1].axvline(cold["@initDuration"].mean(), color="#3B6D11",
                    linestyle=":", linewidth=1.8, label=f"Mean = {cold['@initDuration'].mean():.0f} ms")
    axes[1].set_xlabel("initDuration (ms)")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Cold-Start (initDuration) Distribution")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

plt.tight_layout()
plt.savefig("plots/fig1_cold_start_analysis.png", dpi=150)
print("\n[OK] Saved plots/fig1_cold_start_analysis.png")

# ═════════════════════════════════════════════════════════════════════════════
# 4. PLOT 2 — Duration over time (all requests)
# ═════════════════════════════════════════════════════════════════════════════

fig2, ax = plt.subplots(figsize=(14, 5))
fig2.suptitle("Figure 2 — Execution Duration Over Time", fontsize=14, fontweight="bold")

cw_sorted = cw.sort_values("@timestamp")
idx = np.arange(len(cw_sorted))
colors = np.where(cw_sorted["@initDuration"].notna(), "#E24B4A", "#1D9E75")
ax.scatter(idx, cw_sorted["@duration"], c=colors, s=15, alpha=0.6)

from matplotlib.patches import Patch
ax.legend(handles=[
    Patch(color="#E24B4A", label="Cold start"),
    Patch(color="#1D9E75", label="Warm start"),
], loc="upper right")
ax.set_xlabel("Request number (chronological)")
ax.set_ylabel("Execution Duration (ms)")
ax.set_title("Red = Cold start (initDuration present)  |  Green = Warm start")
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("plots/fig2_duration_over_time.png", dpi=150)
print("[OK] Saved plots/fig2_duration_over_time.png")

# ═════════════════════════════════════════════════════════════════════════════
# 5. PLOT 3 — RTT from traffic log (if available)
# ═════════════════════════════════════════════════════════════════════════════

if traffic is not None and "interval" in traffic.columns:
    fig3, ax = plt.subplots(figsize=(14, 5))
    fig3.suptitle("Figure 3 — Round-Trip Time by Interval", fontsize=14, fontweight="bold")

    intervals = traffic["interval"].unique()
    rtt_by_interval = [traffic[traffic["interval"] == iv]["rtt_ms"].dropna() for iv in intervals]

    ax.boxplot(rtt_by_interval, tick_labels=intervals, patch_artist=True,
               boxprops=dict(facecolor="#9FE1CB", color="#0F6E56"),
               medianprops=dict(color="#E24B4A", linewidth=2))
    ax.set_ylabel("RTT (ms)")
    ax.set_xlabel("Interval")
    ax.set_title("RTT Distribution per Traffic Interval")
    ax.grid(axis="y", alpha=0.4)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig("plots/fig3_rtt_by_interval.png", dpi=150)
    print("[OK] Saved plots/fig3_rtt_by_interval.png")

# ═════════════════════════════════════════════════════════════════════════════
# 6. PLOT 4 — Cold-start % of duration over request sequence
# ═════════════════════════════════════════════════════════════════════════════

if len(cold) > 0:
    fig4, ax = plt.subplots(figsize=(10, 5))
    fig4.suptitle("Figure 4 — Cold-Start % of Execution Duration", fontsize=14, fontweight="bold")
    cold_pct = cold["@initDuration"] / cold["@duration"] * 100
    ax.scatter(range(len(cold_pct)), cold_pct, color="#E8593C", s=20, alpha=0.7)
    ax.axhline(cold_pct.median(), color="#042C53", linestyle="--",
               label=f"Median = {cold_pct.median():.1f}%")
    ax.set_xlabel("Cold-start event #")
    ax.set_ylabel("initDuration / duration x 100 (%)")
    ax.set_title("How much of execution time is Cold-Start overhead?")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("plots/fig4_coldstart_pct.png", dpi=150)
    print("[OK] Saved plots/fig4_coldstart_pct.png")

print("\nAll plots saved in ./plots/")
plt.show()
