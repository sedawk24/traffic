"""Phase 0 toolchain spike + throughput benchmark.

Proves the SUMO/libsumo toolchain works on this machine and records a
representative microscopic throughput number (vehicle-updates/sec) to close the
capacity-assumption gap noted in docs/research/engine-selection.md.

Run with: uv run python scripts/phase0_spike.py
"""

from __future__ import annotations

import os
import random
import subprocess
import time

import libsumo
import sumolib

random.seed(42)
WORK = "data/spike"
os.makedirs(WORK, exist_ok=True)
NET = os.path.join(WORK, "grid.net.xml")


def section(title: str) -> None:
    print(f"\n=== {title} ===")


section("versions + binaries")
print("libsumo:", libsumo.__version__ if hasattr(libsumo, "__version__") else "?")
print("sumolib:", getattr(sumolib, "__version__", "?"))
netgenerate = sumolib.checkBinary("netgenerate")
sumo_bin = sumolib.checkBinary("sumo")
print("netgenerate:", netgenerate)
print("sumo:", sumo_bin)
print("SUMO_HOME:", os.environ.get("SUMO_HOME", "<unset, resolved via sumolib>"))

section("capability check (sumo --help)")
help_txt = subprocess.run([sumo_bin, "--help"], capture_output=True, text=True).stdout.lower()
print("  --fcd-output present:", "--fcd-output" in help_txt)
print("  --fcd-output.geo present:", "--fcd-output.geo" in help_txt)
print("  parquet output mentioned:", "parquet" in help_txt)

section("build 20x20 grid network")
t0 = time.perf_counter()
subprocess.run(
    [netgenerate, "--grid", "--grid.number", "20", "--grid.length", "200",
     "--default.lanenumber", "2", "--tls.guess", "true", "--no-turnarounds", "true",
     "-o", NET],
    check=True, capture_output=True, text=True,
)
print(f"  built in {time.perf_counter() - t0:.2f}s -> {NET}")
net = sumolib.net.readNet(NET)
edges = [e.getID() for e in net.getEdges() if e.allows("passenger") and not e.getID().startswith(":")]
print(f"  drivable edges: {len(edges)}")

section("FCD output sanity (short run, XML)")
fcd_xml = os.path.join(WORK, "fcd.xml")
libsumo.start([sumo_bin, "-n", NET, "--fcd-output", fcd_xml, "--step-length", "1", "--no-step-log", "true"])
for i in range(30):
    libsumo.route.add(f"r{i}", [random.choice(edges)])
    try:
        libsumo.vehicle.add(f"v{i}", f"r{i}", departSpeed="max")
        libsumo.vehicle.changeTarget(f"v{i}", random.choice(edges))
    except Exception:
        pass
for _ in range(60):
    libsumo.simulationStep()
libsumo.close()
fcd_ok = os.path.exists(fcd_xml) and os.path.getsize(fcd_xml) > 0
print(f"  wrote {fcd_xml}: {fcd_ok} ({os.path.getsize(fcd_xml)} bytes)")

# Does SUMO write Parquet FCD directly when the extension is .parquet?
section("FCD Parquet probe")
fcd_pq = os.path.join(WORK, "fcd.parquet")
try:
    r = subprocess.run(
        [sumo_bin, "-n", NET, "--fcd-output", fcd_pq, "--end", "20", "--no-step-log", "true"],
        capture_output=True, text=True,
    )
    pq_ok = os.path.exists(fcd_pq) and os.path.getsize(fcd_pq) > 0
    print(f"  parquet FCD written directly: {pq_ok}")
    if not pq_ok and r.stderr:
        print("  (note)", r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "")
except Exception as exc:  # noqa: BLE001
    print("  parquet probe error:", exc)

section("throughput benchmark (microscopic, libsumo, headless)")
STEPS = 1000
INSERT_PER_STEP = 25
MAX_ACTIVE = 8000
libsumo.start([sumo_bin, "-n", NET, "--step-length", "1", "--no-step-log", "true",
               "--time-to-teleport", "120", "--routing-algorithm", "dijkstra"])
veh_id = 0
total_updates = 0
peak_active = 0
t_start = time.perf_counter()
for step in range(STEPS):
    active = libsumo.vehicle.getIDCount()
    peak_active = max(peak_active, active)
    total_updates += active
    if active < MAX_ACTIVE:
        for _ in range(INSERT_PER_STEP):
            rid = f"br{veh_id}"
            try:
                libsumo.route.add(rid, [random.choice(edges)])
                libsumo.vehicle.add(f"bv{veh_id}", rid, departSpeed="max")
                libsumo.vehicle.changeTarget(f"bv{veh_id}", random.choice(edges))
            except Exception:
                pass
            veh_id += 1
    libsumo.simulationStep()
elapsed = time.perf_counter() - t_start
libsumo.close()

ups = total_updates / elapsed if elapsed else 0
print(f"  steps:            {STEPS}")
print(f"  peak active veh:  {peak_active}")
print(f"  total veh-updates:{total_updates:,}")
print(f"  wall time:        {elapsed:.2f}s")
print(f"  vehicle-updates/sec: {ups:,.0f}")
print(f"  sim-seconds/sec (1s steps): {STEPS / elapsed:,.1f}x real-time at this load")
print("\nDone.")
